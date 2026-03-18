# proposal_routes.py
# Handles:
#   - Auto-generating a proposal PDF when a project is created
#   - Serving the proposal URL for in-portal preview
#   - Recording client agreement before Fund Escrow unlocks
#   - Sending per-milestone + final summary receipts via escrow webhook

import io
import json
import os
import tempfile
from datetime import datetime
from typing import Optional

import boto3
import resend
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.portal_db import get_session, Project, PortalUser
from app.client_portal_routes import get_current_user, require_admin
from app.utils.lawbot_proposal_generator import create_proposal_pdf
from app.utils.lawbot_receipt_generator import create_receipt_pdf

proposal_router = APIRouter(prefix="/api", tags=["proposals"])

# ── B2 client (for existing project files) ───────────────────────────────────
B2_ENDPOINT_URL      = os.getenv("B2_ENDPOINT_URL")
B2_ACCESS_KEY_ID     = os.getenv("B2_ACCESS_KEY_ID")
B2_SECRET_ACCESS_KEY = os.getenv("B2_SECRET_ACCESS_KEY")
B2_BUCKET_NAME       = os.getenv("B2_BUCKET_NAME", "4dgaming-client-files")

# ── AWS S3 client (for proposals & receipts) ─────────────────────────────────
AWS_ACCESS_KEY_ID     = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION            = os.getenv("AWS_REGION", "us-east-1")
AWS_BUCKET_NAME       = os.getenv("AWS_BUCKET_NAME", "lawfirm-docs-2024")

RESEND_API_KEY   = os.getenv("RESEND_API_KEY")
ADMIN_EMAIL      = os.getenv("ADMIN_EMAIL", "4dgamingllc@gmail.com")
FROM_EMAIL       = os.getenv("RESEND_FROM_EMAIL", "noreply@4dgaming.games")
FRONTEND_URL     = "https://4dgaming.games"

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# Validate AWS credentials at startup
print(f"🔍 AWS_ACCESS_KEY_ID set: {bool(AWS_ACCESS_KEY_ID)} ({AWS_ACCESS_KEY_ID[:6] + '...' if AWS_ACCESS_KEY_ID else 'MISSING'})")
print(f"🔍 AWS_SECRET_ACCESS_KEY set: {bool(AWS_SECRET_ACCESS_KEY)}")
print(f"🔍 AWS_REGION: {AWS_REGION}")
print(f"🔍 AWS_BUCKET_NAME: {AWS_BUCKET_NAME}")

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upload_pdf_to_b2(pdf_bytes: bytes, key: str) -> str:
    """Upload PDF bytes to AWS S3 and return public URL."""
    s3.upload_fileobj(
        io.BytesIO(pdf_bytes),
        AWS_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": "application/pdf"},
    )
    return f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}"


def _build_proposal_data(project: Project, owner: PortalUser) -> dict:
    """Build the data dict expected by create_proposal_pdf() from project.notes."""
    try:
        notes = json.loads(project.notes) if project.notes else {}
    except (json.JSONDecodeError, TypeError):
        notes = {}

    pricing    = notes.get("pricing") or {}
    milestones = pricing.get("milestones", [])
    total_price = pricing.get("totalPrice") or pricing.get("total") or sum(m.get("amount", 0) for m in milestones)
    service    = project.service or "lawbot360"

    # ── Add-ons: portal stores as selectedAddons [{id, price, type}] ──────────
    ADDON_LABELS = {
        "nativeapps":       "Native iOS & Android Mobile Apps",
        "multilanguage":    "Multi-Language Support",
        "smswhatsapp":      "SMS / WhatsApp Integration",
        "analytics":        "Advanced Analytics Dashboard",
        "multilocation":    "Multi-Location Support",
        "voicephone":       "Voice / Phone Integration (Twilio)",
        # fallbacks
        "mobile":           "Native iOS & Android Mobile Apps",
        "voice":            "Voice / Phone Integration (Twilio)",
        "whatsapp":         "SMS / WhatsApp Integration",
    }
    raw_addons = pricing.get("selectedAddons") or pricing.get("addons") or []
    addons = []
    for a in raw_addons:
        addon_id    = str(a.get("id", "")).lower().replace("_", "").replace("-", "").replace(" ", "")
        addon_price = float(a.get("price", 0))
        addon_label = a.get("label") or ADDON_LABELS.get(addon_id) or a.get("id", "").replace("_", " ").title()
        if addon_price > 0:
            addons.append({"label": addon_label, "price": addon_price})

    # ── Maintenance: portal stores as subscription {id, label, price} ─────────
    MAINTENANCE_ID_MAP = {
        "maintenance_basic":      "Basic",
        "maintenance_pro":        "Professional",
        "maintenance_enterprise": "Enterprise",
        "none":                   "None",
    }
    subscription = pricing.get("subscription") or {}
    sub_id    = str(subscription.get("id", "")).lower()
    sub_label = subscription.get("label", "")

    # Map to the tier name the generator expects
    if sub_id in MAINTENANCE_ID_MAP:
        maintenance = MAINTENANCE_ID_MAP[sub_id]
    elif "basic" in sub_label.lower():
        maintenance = "Basic"
    elif "professional" in sub_label.lower() or "pro" in sub_label.lower():
        maintenance = "Professional"
    elif "enterprise" in sub_label.lower():
        maintenance = "Enterprise"
    elif sub_id == "none" or not sub_id:
        maintenance = "None"
    else:
        maintenance = pricing.get("maintenance", "None")

    # ── Timeline phases from milestones ───────────────────────────────────────
    phase_names = {
        1: "Discovery & Custom Flow Design",
        2: "Bot Build & System Integrations",
        3: "Testing, Training & Launch",
    }
    timeline_phases = []
    for i, ms in enumerate(milestones, start=1):
        weeks = ms.get("weeksFromStart", i * 0.5)
        timeline_phases.append({
            "name":        ms.get("name", phase_names.get(i, f"Milestone {i}")),
            "duration":    f"Week {weeks}",
            "deliverables": ms.get("description", ""),
        })

    proposal_number = f"4DG-{project.id:04d}"

    return {
        "proposal_number":       proposal_number,
        "firm_name":             notes.get("firm_name") or owner.name,
        "contact_name":          notes.get("contact_name") or owner.name,
        "contact_email":         notes.get("contact_email") or owner.email,
        "contact_phone":         notes.get("contact_phone"),
        "current_intake_method": notes.get("description") or notes.get("brief_description"),
        "practice_areas":        notes.get("practice_areas") or [service],
        "addons":                addons,
        "timeline_weeks":        int(pricing.get("timelineWeeks") or max((m.get("weeksFromStart", 2) for m in milestones), default=6)),
        "timeline_phases":       timeline_phases,
        "total_price":           float(total_price),
        "maintenance_tier":      maintenance,
        "subscription_label":    sub_label,
        "subscription_price":    float(subscription.get("price", 0)),
        # Project detail fields from the portal form
        "crm":                   notes.get("crm") or notes.get("current_crm"),
        "scheduling_system":     notes.get("scheduling_system") or notes.get("calendar_system"),
        "payment_processor":     notes.get("payment_processor") or notes.get("preferred_payment"),
        "website_url":           notes.get("website_url") or notes.get("law_firm_website"),
        "practice_areas_text":   notes.get("practice_areas_text") or notes.get("primary_practice_areas"),
        "special_requirements":  notes.get("special_requirements") or notes.get("special_reqs"),
        "monthly_visitors":      notes.get("monthly_visitors") or notes.get("approximate_monthly_visitors"),
    }


def generate_and_store_proposal(project: Project, owner: PortalUser, db: Session) -> str:
    """
    Generate proposal PDF, upload to B2, store URL on project.
    Returns the public URL.
    Called automatically after project creation.
    """
    data = _build_proposal_data(project, owner)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        create_proposal_pdf(tmp_path, data)
        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()
    finally:
        import os as _os
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass

    key = f"proposals/project-{project.id}/proposal-{project.id}.pdf"
    url = _upload_pdf_to_b2(pdf_bytes, key)

    project.proposal_pdf_key = key
    project.proposal_pdf_url = url
    db.add(project)
    db.commit()
    db.refresh(project)

    print(f"✅ Proposal generated for project {project.id}: {url}")
    return url


# ── Routes ────────────────────────────────────────────────────────────────────

@proposal_router.get("/projects/{project_id}/proposal")
def get_proposal(
    project_id: int,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Return the proposal PDF URL for in-portal preview."""
    project = db.get(Project, project_id)
    if not project or (project.owner_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.proposal_pdf_url:
        # Generate on demand if missing
        owner = db.get(PortalUser, project.owner_id)
        url = generate_and_store_proposal(project, owner, db)
    else:
        url = project.proposal_pdf_url

    return {
        "proposal_url":    url,
        "proposal_agreed": project.proposal_agreed,
        "proposal_agreed_at": project.proposal_agreed_at,
    }


@proposal_router.post("/projects/{project_id}/proposal/agree")
def agree_to_proposal(
    project_id: int,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Client agrees to the proposal — unlocks the Fund Escrow button."""
    project = db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.proposal_pdf_url:
        raise HTTPException(status_code=400, detail="Proposal not yet generated")

    if project.proposal_agreed:
        return {"ok": True, "already_agreed": True}

    project.proposal_agreed    = True
    project.proposal_agreed_at = datetime.utcnow()
    db.add(project)
    db.commit()

    print(f"✅ Project {project_id} proposal agreed by {current_user.email}")
    return {"ok": True, "agreed_at": project.proposal_agreed_at}


@proposal_router.post("/projects/{project_id}/proposal/regenerate")
def regenerate_proposal(
    project_id: int,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """Admin: regenerate proposal PDF (e.g. after pricing changes)."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    owner = db.get(PortalUser, project.owner_id)
    url = generate_and_store_proposal(project, owner, db)
    return {"ok": True, "proposal_url": url}


# ── Receipt helpers ───────────────────────────────────────────────────────────

def _send_receipt_email(to_email: str, client_name: str, subject: str, pdf_url: str, body_html: str):
    """Send receipt email with PDF link via Resend."""
    if not RESEND_API_KEY:
        print("⚠️  Resend not configured — skipping receipt email")
        return
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": body_html,
        })
        print(f"✅ Receipt email sent to {to_email}")
    except Exception as e:
        print(f"⚠️  Receipt email failed: {e}")


def send_milestone_receipt(
    project: Project,
    owner: PortalUser,
    milestone_number: int,
    milestone_name: str,
    amount: float,
    escrow_transaction_id: str,
    db: Session,
):
    """Generate + email a per-milestone receipt when escrow releases funds."""
    try:
        notes = json.loads(project.notes) if project.notes else {}
    except Exception:
        notes = {}

    pricing     = notes.get("pricing") or {}
    total_price = pricing.get("total", 0)
    addons      = pricing.get("addons", [])
    service     = project.service or "LawBot 360"

    receipt_data = {
        "receipt_number":    f"RCP-{project.id}-M{milestone_number}",
        "firm_name":         notes.get("firm_name") or owner.name,
        "contact_name":      owner.name,
        "contact_email":     owner.email,
        "payment_date":      datetime.utcnow().strftime("%B %d, %Y"),
        "payment_method":    "Escrow.com",
        "service_type":      service,
        "addons":            addons if milestone_number == 1 else [],
        "milestone":         milestone_name,
        "amount":            float(amount),
        "total_project_cost": float(total_price),
        "transaction_id":    escrow_transaction_id,
        "notes":             f"Milestone {milestone_number} of 3 completed and approved.",
    }

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        create_receipt_pdf(tmp_path, receipt_data)
        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()
    finally:
        import os as _os
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass

    key = f"receipts/project-{project.id}/receipt-milestone-{milestone_number}.pdf"
    url = _upload_pdf_to_b2(pdf_bytes, key)

    subject = f"4D Gaming Receipt — {project.name} Milestone {milestone_number}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:30px;border-radius:8px 8px 0 0;text-align:center;">
        <h1 style="margin:0;">✅ Milestone {milestone_number} Complete!</h1>
      </div>
      <div style="background:#f9fafb;padding:30px;border-radius:0 0 8px 8px;">
        <p>Hi {owner.name},</p>
        <p>Milestone <strong>{milestone_number} — {milestone_name}</strong> has been delivered and approved.
           Escrow.com has released <strong>${amount:,.2f}</strong> to 4D Gaming.</p>
        <div style="background:white;padding:20px;border-radius:8px;margin:20px 0;border-left:4px solid #667eea;">
          <p style="margin:0;"><strong>Project:</strong> {project.name}</p>
          <p style="margin:8px 0 0;"><strong>Amount Released:</strong> ${amount:,.2f}</p>
          <p style="margin:8px 0 0;"><strong>Escrow Transaction:</strong> {escrow_transaction_id}</p>
        </div>
        <p style="text-align:center;">
          <a href="{url}" style="background:#667eea;color:white;padding:12px 28px;text-decoration:none;border-radius:6px;display:inline-block;font-weight:bold;">
            Download Receipt PDF
          </a>
        </p>
        <p style="color:#6b7280;font-size:13px;">Questions? Reply to this email or call (504) 383-3692.</p>
      </div>
    </div>
    """

    _send_receipt_email(owner.email, owner.name, subject, url, html)
    # Also notify admin
    _send_receipt_email(ADMIN_EMAIL, "Admin", f"[ADMIN] {subject}", url, html)
    return url


def send_final_receipt(
    project: Project,
    owner: PortalUser,
    escrow_transaction_id: str,
    db: Session,
):
    """Generate + email a final summary receipt when all milestones are complete."""
    try:
        notes = json.loads(project.notes) if project.notes else {}
    except Exception:
        notes = {}

    pricing     = notes.get("pricing") or {}
    milestones  = pricing.get("milestones", [])
    total_price = pricing.get("total", sum(m.get("amount", 0) for m in milestones))
    addons      = pricing.get("addons", [])
    service     = project.service or "LawBot 360"

    receipt_data = {
        "receipt_number":    f"RCP-{project.id}-FINAL",
        "firm_name":         notes.get("firm_name") or owner.name,
        "contact_name":      owner.name,
        "contact_email":     owner.email,
        "payment_date":      datetime.utcnow().strftime("%B %d, %Y"),
        "payment_method":    "Escrow.com",
        "service_type":      service,
        "addons":            addons,
        "milestone":         "All Milestones — Project Complete",
        "amount":            float(total_price),
        "total_project_cost": float(total_price),
        "transaction_id":    escrow_transaction_id,
        "notes":             "All milestones have been delivered, approved, and paid in full. Your LawBot 360 system is live!",
    }

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        create_receipt_pdf(tmp_path, receipt_data)
        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()
    finally:
        import os as _os
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass

    key = f"receipts/project-{project.id}/receipt-final.pdf"
    url = _upload_pdf_to_b2(pdf_bytes, key)

    subject = f"🎉 4D Gaming — Project Complete! Final Receipt for {project.name}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:linear-gradient(135deg,#10b981,#059669);color:white;padding:30px;border-radius:8px 8px 0 0;text-align:center;">
        <h1 style="margin:0;">🎉 Project Complete!</h1>
      </div>
      <div style="background:#f9fafb;padding:30px;border-radius:0 0 8px 8px;">
        <p>Hi {owner.name},</p>
        <p>All milestones for <strong>{project.name}</strong> have been delivered, approved,
           and paid in full. Your system is live!</p>
        <div style="background:white;padding:20px;border-radius:8px;margin:20px 0;border-left:4px solid #10b981;">
          <p style="margin:0;"><strong>Project:</strong> {project.name}</p>
          <p style="margin:8px 0 0;"><strong>Total Paid:</strong> ${total_price:,.2f}</p>
          <p style="margin:8px 0 0;"><strong>Escrow Transaction:</strong> {escrow_transaction_id}</p>
        </div>
        <p style="text-align:center;">
          <a href="{url}" style="background:#10b981;color:white;padding:12px 28px;text-decoration:none;border-radius:6px;display:inline-block;font-weight:bold;">
            Download Final Receipt PDF
          </a>
        </p>
        <p>Thank you for choosing 4D Gaming. We're here if you need anything!</p>
      </div>
    </div>
    """

    _send_receipt_email(owner.email, owner.name, subject, url, html)
    _send_receipt_email(ADMIN_EMAIL, "Admin", f"[ADMIN] {subject}", url, html)
    return url