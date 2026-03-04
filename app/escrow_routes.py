# escrow_routes.py
# Escrow.com routes for 4D Gaming — single-transaction model.
#
# Register BOTH routers in main.py:
#   from app.escrow_routes import escrow_router, client_escrow_router
#   app.include_router(escrow_router, prefix="/api/escrow")   # admin + webhook
#   app.include_router(client_escrow_router, prefix="/api")   # client button calls

import json
import hmac
import hashlib
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from app.portal_db import get_session, PortalUser, Project
from app.client_portal_routes import get_current_user, require_admin
from app.escrow_db import EscrowProject, EscrowMilestone
import app.escrow_service as escrow

ESCROW_WEBHOOK_SECRET = os.getenv("ESCROW_WEBHOOK_SECRET", "")

escrow_router        = APIRouter(tags=["escrow-admin"])
client_escrow_router = APIRouter(tags=["escrow-client"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class MilestoneOut(BaseModel):
    id: int
    project_id: int
    milestone_number: int
    milestone_name: str
    amount: float
    percent: float
    escrow_item_id: Optional[str]
    status: str
    delivered_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectEscrowOut(BaseModel):
    id: int
    project_id: int
    escrow_transaction_id: str
    total_amount: float
    funding_url: Optional[str]
    status: str
    created_at: datetime
    funded_at: Optional[datetime]
    milestones: List[MilestoneOut] = []

    class Config:
        from_attributes = True


class AdminSetupRequest(BaseModel):
    project_id: int
    total_amount: float
    schedule: Optional[List[float]] = None          # defaults [0.30, 0.50, 0.20]
    milestone_names: Optional[List[str]] = None
    inspection_days: int = 5


# ── Admin: Set up full project escrow (creates single Escrow.com transaction) ─

@escrow_router.post("/admin/setup")
async def admin_setup_project_escrow(
    data: AdminSetupRequest,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """
    Admin: Create ONE Escrow.com transaction covering the full project amount.
    All milestones are items inside that single transaction.
    Client funds everything at once via one payment link.
    """
    project = db.get(Project, data.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    owner = db.get(PortalUser, project.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Project owner not found")

    existing = db.exec(
        select(EscrowProject).where(EscrowProject.project_id == data.project_id)
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Escrow already set up for this project (txn: {existing.escrow_transaction_id})"
        )

    try:
        milestones = escrow.calculate_milestone_amounts(
            total_amount=data.total_amount,
            schedule=data.schedule,
            milestone_names=data.milestone_names,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        tx = escrow.create_project_transaction(
            project_id=data.project_id,
            project_name=project.name,
            client_email=owner.email,
            client_name=owner.name or owner.email,
            milestones=milestones,
            inspection_days=data.inspection_days,
        )
    except escrow.EscrowAPIError as e:
        raise HTTPException(status_code=502, detail=f"Escrow API error: {e.detail}")

    funding_url = escrow.get_funding_url(tx)
    item_ids = escrow.get_item_ids(tx)

    # Save project-level record
    ep = EscrowProject(
        project_id=data.project_id,
        user_id=project.owner_id,
        escrow_transaction_id=str(tx["id"]),
        total_amount=data.total_amount,
        funding_url=funding_url,
        status="created",
        raw_status=tx.get("status"),
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)

    # Save per-milestone records
    ms_records = []
    for m in milestones:
        ms_rec = EscrowMilestone(
            escrow_project_id=ep.id,
            project_id=data.project_id,
            milestone_number=m["number"],
            milestone_name=m["name"],
            amount=m["amount"],
            percent=m["percent"],
            escrow_item_id=item_ids.get(m["number"]),
            status="pending",
        )
        db.add(ms_rec)
        ms_records.append(ms_rec)

    db.commit()

    return {
        "message": "Escrow transaction created. Send the funding_url to your client.",
        "escrow_transaction_id": str(tx["id"]),
        "total_amount": data.total_amount,
        "funding_url": funding_url,
        "milestones": [
            {
                "number": m["number"],
                "name": m["name"],
                "amount": m["amount"],
                "percent": m["percent"],
                "item_id": item_ids.get(m["number"]),
            }
            for m in milestones
        ],
    }


# ── Admin: Mark a milestone as delivered ─────────────────────────────────────

@escrow_router.post("/admin/deliver/{milestone_id}")
async def admin_mark_delivered(
    milestone_id: int,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """
    Admin: Mark a milestone item as delivered on Escrow.com.
    Starts the client's inspection period (default 5 days).
    Call this when you've completed a milestone.
    """
    ms = db.get(EscrowMilestone, milestone_id)
    if not ms:
        raise HTTPException(status_code=404, detail="Milestone record not found")

    ep = db.get(EscrowProject, ms.escrow_project_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Escrow project not found")

    if ms.status not in ("pending", "funded"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot mark delivered from status '{ms.status}'"
        )

    if not ms.escrow_item_id:
        raise HTTPException(status_code=400, detail="No escrow_item_id on this milestone")

    try:
        escrow.mark_item_delivered(ep.escrow_transaction_id, ms.escrow_item_id)
    except escrow.EscrowAPIError as e:
        raise HTTPException(status_code=502, detail=f"Escrow API error: {e.detail}")

    ms.status = "delivered"
    ms.delivered_at = datetime.utcnow()
    ms.updated_at = datetime.utcnow()
    db.add(ms)
    db.commit()
    db.refresh(ms)

    return {
        "message": f"Milestone {ms.milestone_number} marked as delivered. Client inspection period has started.",
        "milestone_id": milestone_id,
        "milestone_number": ms.milestone_number,
        "status": ms.status,
    }


# ── Admin: Get project escrow status ─────────────────────────────────────────

@escrow_router.get("/admin/project/{project_id}")
async def admin_get_project(
    project_id: int,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """Admin: Get full escrow status for a project including all milestones."""
    ep = db.exec(
        select(EscrowProject).where(EscrowProject.project_id == project_id)
    ).first()
    if not ep:
        raise HTTPException(status_code=404, detail="No escrow set up for this project")

    milestones = db.exec(
        select(EscrowMilestone)
        .where(EscrowMilestone.escrow_project_id == ep.id)
        .order_by(EscrowMilestone.milestone_number)
    ).all()

    return {
        "escrow_transaction_id": ep.escrow_transaction_id,
        "total_amount": ep.total_amount,
        "funding_url": ep.funding_url,
        "status": ep.status,
        "funded_at": ep.funded_at,
        "milestones": [
            {
                "id": m.id,
                "number": m.milestone_number,
                "name": m.milestone_name,
                "amount": m.amount,
                "percent": m.percent,
                "item_id": m.escrow_item_id,
                "status": m.status,
                "delivered_at": m.delivered_at,
                "completed_at": m.completed_at,
            }
            for m in milestones
        ],
    }


# ── Admin: Manual sync from Escrow.com API ───────────────────────────────────

@escrow_router.post("/admin/sync/{project_id}")
async def admin_sync(
    project_id: int,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """Admin: Pull latest status from Escrow.com and update DB records."""
    ep = db.exec(
        select(EscrowProject).where(EscrowProject.project_id == project_id)
    ).first()
    if not ep:
        raise HTTPException(status_code=404, detail="No escrow for this project")

    try:
        tx = escrow.get_transaction(ep.escrow_transaction_id)
    except escrow.EscrowAPIError as e:
        raise HTTPException(status_code=502, detail=f"Escrow API error: {e.detail}")

    raw = tx.get("status", "")
    ep.status = escrow.map_status(raw)
    ep.raw_status = raw
    ep.updated_at = datetime.utcnow()
    if ep.status == "funded" and not ep.funded_at:
        ep.funded_at = datetime.utcnow()
    db.add(ep)

    # Sync per-item statuses
    api_items = {str(item["id"]): item for item in tx.get("items", [])}
    milestones = db.exec(
        select(EscrowMilestone).where(EscrowMilestone.escrow_project_id == ep.id)
    ).all()

    for ms in milestones:
        api_item = api_items.get(ms.escrow_item_id or "")
        if api_item:
            item_raw = api_item.get("status", {})
            # Item status can be a dict or string depending on API version
            item_status = item_raw if isinstance(item_raw, str) else item_raw.get("status", "")
            ms.status = escrow.map_status(item_status)
            ms.updated_at = datetime.utcnow()
            db.add(ms)

    db.commit()
    return {"message": "Synced", "status": ep.status}


# ── Webhook ───────────────────────────────────────────────────────────────────

@escrow_router.post("/webhook")
async def escrow_webhook(
    request: Request,
    db: Session = Depends(get_session),
):
    """
    Escrow.com webhook receiver.
    Configure in Escrow.com dashboard → Settings → Webhooks:
      URL: https://4dgaming.games/api/escrow/webhook
    """
    body = await request.body()

    if ESCROW_WEBHOOK_SECRET:
        sig = request.headers.get("X-Escrow-Signature", "")
        expected = hmac.new(
            ESCROW_WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    escrow_tx_id = str(payload.get("transaction_id") or payload.get("id", ""))
    raw_status   = payload.get("status", "")
    item_id      = str(payload.get("item_id", ""))

    if not escrow_tx_id:
        return {"status": "ignored"}

    ep = db.exec(
        select(EscrowProject).where(EscrowProject.escrow_transaction_id == escrow_tx_id)
    ).first()

    if not ep:
        print(f"⚠️ Escrow webhook: no project for txn {escrow_tx_id}")
        return {"status": "ignored"}

    simplified = escrow.map_status(raw_status)
    now = datetime.utcnow()

    # Update project-level status
    ep.status = simplified
    ep.raw_status = raw_status
    ep.updated_at = now
    if simplified == "funded" and not ep.funded_at:
        ep.funded_at = now
        # When funded, mark all milestones as funded too
        milestones = db.exec(
            select(EscrowMilestone).where(EscrowMilestone.escrow_project_id == ep.id)
        ).all()
        for ms in milestones:
            if ms.status == "pending":
                ms.status = "funded"
                ms.updated_at = now
                db.add(ms)

    elif simplified == "completed" and not ep.completed_at:
        ep.completed_at = now

    db.add(ep)

    # If a specific item was updated, update that milestone
    if item_id:
        ms = db.exec(
            select(EscrowMilestone).where(EscrowMilestone.escrow_item_id == item_id)
        ).first()
        if ms:
            ms.status = simplified
            ms.updated_at = now
            if simplified == "completed" and not ms.completed_at:
                ms.completed_at = now
            db.add(ms)

    db.commit()
    print(f"✅ Escrow webhook: txn={escrow_tx_id} item={item_id} → {simplified}")
    return {"status": "ok"}


# ── Client: view escrow status for their project ──────────────────────────────

@client_escrow_router.get("/projects/{project_id}/escrow/status")
async def client_get_escrow(
    project_id: int,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Client: get escrow status + funding URL for their project."""
    project = db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    ep = db.exec(
        select(EscrowProject).where(EscrowProject.project_id == project_id)
    ).first()

    if not ep:
        return {"status": "not_setup", "milestones": []}

    milestones = db.exec(
        select(EscrowMilestone)
        .where(EscrowMilestone.escrow_project_id == ep.id)
        .order_by(EscrowMilestone.milestone_number)
    ).all()

    return {
        "escrow_transaction_id": ep.escrow_transaction_id,
        "total_amount": ep.total_amount,
        "funding_url": ep.funding_url,
        "status": ep.status,
        "funded_at": ep.funded_at,
        "milestones": [
            {
                "number": m.milestone_number,
                "name": m.milestone_name,
                "amount": m.amount,
                "percent": m.percent,
                "status": m.status,
                "delivered_at": m.delivered_at,
                "completed_at": m.completed_at,
            }
            for m in milestones
        ],
    }


# ── Client: the Fund Escrow button in client-portal.html ─────────────────────
# Called by: POST /api/projects/{id}/escrow/create
# If escrow is already set up, returns the existing funding URL.
# If not yet set up (admin hasn't run /admin/setup), returns 404 with clear message.

@client_escrow_router.post("/projects/{project_id}/escrow/create")
async def client_fund_escrow(
    project_id: int,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """
    Called when client clicks 'Fund Escrow' button.
    Returns the Escrow.com funding URL for the full project amount.
    Admin must have called /api/escrow/admin/setup first.
    """
    project = db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    ep = db.exec(
        select(EscrowProject).where(EscrowProject.project_id == project_id)
    ).first()

    if not ep:
        raise HTTPException(
            status_code=404,
            detail="Escrow has not been set up for this project yet. Your project manager will send you the funding link when ready."
        )

    if ep.status == "completed":
        raise HTTPException(status_code=400, detail="All milestones have been completed.")

    milestones = db.exec(
        select(EscrowMilestone)
        .where(EscrowMilestone.escrow_project_id == ep.id)
        .order_by(EscrowMilestone.milestone_number)
    ).all()

    return {
        "escrow_transaction_id": ep.escrow_transaction_id,
        "total_amount": ep.total_amount,
        "status": ep.status,
        "checkout_url": ep.funding_url,
        "milestones": [
            {
                "number": m.milestone_number,
                "name": m.milestone_name,
                "amount": m.amount,
                "status": m.status,
            }
            for m in milestones
        ],
        "message": (
            "Please fund the full project amount on Escrow.com. "
            "Funds are held securely and released to 4D Gaming as each milestone is completed and approved."
        ),
    }


# ── Backward-compat: client portal HTML calls GET /api/escrow/project/{id} ───
# This was the old route path. Alias it so the HTML doesn't need updating.
@escrow_router.get("/project/{project_id}")
async def compat_get_project_escrow(
    project_id: int,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """
    Backward-compatible alias for the client portal escrow section.
    Returns milestone list in the format expected by renderEscrowSection() in client-portal.html.
    """
    project = db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    ep = db.exec(
        select(EscrowProject).where(EscrowProject.project_id == project_id)
    ).first()

    if not ep:
        return []   # HTML handles empty array gracefully

    milestones = db.exec(
        select(EscrowMilestone)
        .where(EscrowMilestone.escrow_project_id == ep.id)
        .order_by(EscrowMilestone.milestone_number)
    ).all()

    # Shape matches what renderMilestoneCard() in client-portal.html expects
    return [
        {
            "id": m.id,
            "project_id": m.project_id,
            "milestone_number": m.milestone_number,
            "milestone_name": m.milestone_name,
            "milestone_percent": m.percent,
            "amount_usd": m.amount,
            "escrow_transaction_id": ep.escrow_transaction_id,
            "escrow_item_id": m.escrow_item_id,
            "funding_url": ep.funding_url,
            "escrow_status": m.status,
            "funded_at": ep.funded_at.isoformat() if ep.funded_at else None,
            "delivered_at": m.delivered_at.isoformat() if m.delivered_at else None,
            "completed_at": m.completed_at.isoformat() if m.completed_at else None,
            "created_at": m.created_at.isoformat(),
        }
        for m in milestones
    ]