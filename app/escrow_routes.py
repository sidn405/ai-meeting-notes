"""
escrow_routes.py — Escrow.com milestone payment routes for 4D Gaming.

Register in main.py:
    from app.escrow_routes import escrow_router
    app.include_router(escrow_router)

ENV vars to add to Railway:
    ESCROW_EMAIL=your@email.com
    ESCROW_API_KEY=your_escrow_api_key
    ESCROW_WEBHOOK_SECRET=optional_webhook_secret

Stripe routes are NOT modified — both systems coexist.
"""

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
from app.escrow_db import EscrowTransaction
import app.escrow_service as escrow

ESCROW_WEBHOOK_SECRET = os.getenv("ESCROW_WEBHOOK_SECRET", "")

escrow_router = APIRouter(prefix="/api/escrow", tags=["escrow-payments"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class EscrowTransactionOut(BaseModel):
    id: int
    project_id: int
    milestone_number: int
    milestone_name: str
    milestone_percent: float
    amount_usd: float
    escrow_transaction_id: Optional[str]
    funding_url: Optional[str]
    escrow_status: str
    funded_at: Optional[datetime]
    delivered_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class SetupMilestonesRequest(BaseModel):
    project_id: int
    total_amount: float
    schedule: Optional[List[float]] = None          # defaults to [0.30, 0.50, 0.20]
    milestone_names: Optional[List[str]] = None     # optional custom names
    inspection_days: int = 5


class CreateSingleMilestoneRequest(BaseModel):
    project_id: int
    milestone_number: int
    milestone_name: str
    amount_usd: float
    inspection_days: int = 5
    notes: Optional[str] = None


# ── Admin routes ───────────────────────────────────────────────────────────────

@escrow_router.post("/admin/setup-milestones", response_model=List[EscrowTransactionOut])
async def admin_setup_all_milestones(
    data: SetupMilestonesRequest,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """
    Admin: Create Escrow.com transactions for ALL milestones at once.
    Default schedule: 30% / 50% / 20%. Pass `schedule` to override.
    Each milestone gets its own transaction + funding URL.
    """
    project = db.get(Project, data.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    owner = db.get(PortalUser, project.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Project owner not found")

    existing = db.exec(
        select(EscrowTransaction).where(EscrowTransaction.project_id == data.project_id)
    ).all()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Escrow milestones already exist for this project ({len(existing)} found)."
        )

    try:
        milestones = escrow.calculate_milestone_amounts(
            total_amount=data.total_amount,
            schedule=data.schedule,
            milestone_names=data.milestone_names,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    created = []
    for m in milestones:
        try:
            tx = escrow.create_milestone_transaction(
                project_id=data.project_id,
                project_name=project.name,
                milestone_number=m["number"],
                milestone_name=m["name"],
                amount_usd=m["amount"],
                client_email=owner.email,
                client_name=owner.name,
                inspection_days=data.inspection_days,
            )
            items = tx.get("items", [])
            item_id = str(items[0].get("id", "")) if items else None
            funding_url = escrow.get_funding_url(tx)

            record = EscrowTransaction(
                project_id=data.project_id,
                user_id=project.owner_id,
                milestone_number=m["number"],
                milestone_name=m["name"],
                milestone_percent=m["percent"],
                amount_usd=m["amount"],
                escrow_transaction_id=str(tx["id"]),
                escrow_item_id=item_id,
                funding_url=funding_url,
                escrow_status="created",
                escrow_raw_status=tx.get("status"),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            created.append(record)

        except escrow.EscrowAPIError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Escrow API error on milestone {m['number']}: {e.detail}"
            )

    _sync_project_notes(project, milestones, data.total_amount, db)
    return created


@escrow_router.post("/admin/milestone", response_model=EscrowTransactionOut)
async def admin_create_single_milestone(
    data: CreateSingleMilestoneRequest,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """Admin: Create a single milestone escrow transaction (for custom schedules)."""
    project = db.get(Project, data.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    owner = db.get(PortalUser, project.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Project owner not found")

    dupe = db.exec(
        select(EscrowTransaction).where(
            EscrowTransaction.project_id == data.project_id,
            EscrowTransaction.milestone_number == data.milestone_number,
        )
    ).first()
    if dupe:
        raise HTTPException(status_code=400, detail=f"Milestone {data.milestone_number} already exists")

    try:
        tx = escrow.create_milestone_transaction(
            project_id=data.project_id,
            project_name=project.name,
            milestone_number=data.milestone_number,
            milestone_name=data.milestone_name,
            amount_usd=data.amount_usd,
            client_email=owner.email,
            client_name=owner.name,
            inspection_days=data.inspection_days,
            notes=data.notes,
        )
    except escrow.EscrowAPIError as e:
        raise HTTPException(status_code=502, detail=f"Escrow API error: {e.detail}")

    items = tx.get("items", [])
    item_id = str(items[0].get("id", "")) if items else None
    funding_url = escrow.get_funding_url(tx)

    record = EscrowTransaction(
        project_id=data.project_id,
        user_id=project.owner_id,
        milestone_number=data.milestone_number,
        milestone_name=data.milestone_name,
        milestone_percent=0.0,
        amount_usd=data.amount_usd,
        escrow_transaction_id=str(tx["id"]),
        escrow_item_id=item_id,
        funding_url=funding_url,
        escrow_status="created",
        escrow_raw_status=tx.get("status"),
        notes=data.notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@escrow_router.post("/admin/deliver/{db_id}", response_model=EscrowTransactionOut)
async def admin_mark_delivered(
    db_id: int,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """
    Admin: Mark milestone as delivered on Escrow.com.
    Call this when you finish building a milestone — starts the client's inspection period.
    After inspection_days, if client doesn't dispute, funds auto-release.
    """
    record = db.get(EscrowTransaction, db_id)
    if not record:
        raise HTTPException(status_code=404, detail="Escrow transaction not found")

    if record.escrow_status not in ("funded", "in_progress", "created"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot mark delivered from status '{record.escrow_status}'"
        )

    if not record.escrow_transaction_id or not record.escrow_item_id:
        raise HTTPException(status_code=400, detail="Missing escrow transaction/item ID")

    try:
        escrow.mark_milestone_delivered(record.escrow_transaction_id, record.escrow_item_id)
    except escrow.EscrowAPIError as e:
        raise HTTPException(status_code=502, detail=f"Escrow API error: {e.detail}")

    record.escrow_status = "delivered"
    record.delivered_at = datetime.utcnow()
    record.updated_at = datetime.utcnow()
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@escrow_router.get("/admin/project/{project_id}", response_model=List[EscrowTransactionOut])
async def admin_get_project_escrow(
    project_id: int,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """Admin: List all escrow milestones for a project."""
    records = db.exec(
        select(EscrowTransaction)
        .where(EscrowTransaction.project_id == project_id)
        .order_by(EscrowTransaction.milestone_number)
    ).all()
    return records


@escrow_router.post("/admin/sync/{db_id}", response_model=EscrowTransactionOut)
async def admin_sync_status(
    db_id: int,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """Admin: Manually sync a transaction's status from Escrow.com API (if webhook missed it)."""
    record = db.get(EscrowTransaction, db_id)
    if not record or not record.escrow_transaction_id:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        tx = escrow.get_transaction(record.escrow_transaction_id)
        raw = tx.get("status", "")
        simplified = _map_status(raw)
        _apply_status(record, simplified, raw)
        db.add(record)
        db.commit()
        db.refresh(record)
    except escrow.EscrowAPIError as e:
        raise HTTPException(status_code=502, detail=f"Escrow API error: {e.detail}")

    return record


# ── Client routes ──────────────────────────────────────────────────────────────

@escrow_router.get("/project/{project_id}", response_model=List[EscrowTransactionOut])
async def client_get_project_escrow(
    project_id: int,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Client: View escrow milestone status + funding URLs for their project."""
    project = db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    records = db.exec(
        select(EscrowTransaction)
        .where(EscrowTransaction.project_id == project_id)
        .order_by(EscrowTransaction.milestone_number)
    ).all()
    return records


# ── Webhook ────────────────────────────────────────────────────────────────────

@escrow_router.post("/webhook")
async def escrow_webhook(
    request: Request,
    db: Session = Depends(get_session),
):
    """
    Escrow.com webhook. Configure in your Escrow.com dashboard:
    Webhook URL: https://4dgaming.games/api/escrow/webhook
    """
    body = await request.body()

    if ESCROW_WEBHOOK_SECRET:
        sig = request.headers.get("X-Escrow-Signature", "")
        expected = hmac.new(
            ESCROW_WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    escrow_tx_id = str(payload.get("transaction_id") or payload.get("id", ""))
    raw_status = payload.get("status", "")

    if not escrow_tx_id:
        return {"status": "ignored"}

    record = db.exec(
        select(EscrowTransaction)
        .where(EscrowTransaction.escrow_transaction_id == escrow_tx_id)
    ).first()

    if not record:
        print(f"⚠️ Escrow webhook: no record for {escrow_tx_id}")
        return {"status": "ignored", "reason": "not found"}

    simplified = _map_status(raw_status)
    _apply_status(record, simplified, raw_status)
    db.add(record)
    db.commit()

    print(f"✅ Escrow webhook: {escrow_tx_id} → {simplified}")
    return {"status": "ok"}


# ── Internal helpers ───────────────────────────────────────────────────────────

def _map_status(raw: str) -> str:
    return {
        "new": "created",
        "in_progress": "in_progress",
        "funded": "funded",
        "shipped": "delivered",
        "received": "inspection",
        "completed": "completed",
        "cancelled": "cancelled",
        "disputed": "disputed",
    }.get(raw.lower(), raw.lower())


def _apply_status(record: EscrowTransaction, simplified: str, raw: str):
    now = datetime.utcnow()
    record.escrow_status = simplified
    record.escrow_raw_status = raw
    record.updated_at = now
    if simplified == "funded" and not record.funded_at:
        record.funded_at = now
    elif simplified == "delivered" and not record.delivered_at:
        record.delivered_at = now
    elif simplified == "completed" and not record.completed_at:
        record.completed_at = now
    elif simplified == "cancelled" and not record.cancelled_at:
        record.cancelled_at = now


def _sync_project_notes(project: Project, milestones: list, total: float, db: Session):
    """Write escrow milestone schedule into project.notes for portal display."""
    try:
        notes = json.loads(project.notes) if project.notes else {}
    except (json.JSONDecodeError, TypeError):
        notes = {}

    notes["payment_method"] = "escrow"
    notes["pricing"] = {
        "total": total,
        "milestones": [
            {
                "name": m["name"],
                "amount": m["amount"],
                "percent": m["percent"],
                "weeksFromStart": m["number"],
            }
            for m in milestones
        ],
    }
    project.notes = json.dumps(notes)
    db.add(project)
    db.commit()