# app/services/emailer.py
import os, base64, mimetypes, smtplib
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
import httpx
from ..config import get_settings

settings = get_settings()

# --- Dev outbox (always available) ---
OUTBOX_DIR = (Path(__file__).resolve().parents[2] / "data" / "outbox" / "email")
OUTBOX_DIR.mkdir(parents=True, exist_ok=True)

def _dev_write(to_email: str, subject: str, body_text: str, body_html: str | None, attachments: list[str] | None):
    safe_to = to_email.replace("@", "_at_")
    fname = OUTBOX_DIR / f"email_to={safe_to}_{subject.replace(' ','_')}.eml"
    lines = [f"TO: {to_email}", f"SUBJECT: {subject}", ""]
    lines.append(body_text or "")
    if body_html:
        lines.append("\n[HTML PART]\n" + body_html)
    if attachments:
        lines.append("\n[ATTACHMENTS]\n" + "\n".join(attachments))
    fname.write_text("\n".join(lines), encoding="utf-8")

# --- SMTP (fallback) ---
def _smtp_send(to_email: str, subject: str, body_text: str, body_html: str | None, attachments: list[str] | None):
    if not (settings.smtp_host and settings.smtp_user and settings.smtp_pass and settings.from_email):
        _dev_write(to_email, subject, body_text, body_html, attachments)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(("Meeting Notes", settings.from_email))
    msg["To"] = to_email

    if body_html:
        msg.set_content(body_text or "", subtype="plain", charset="utf-8")
        msg.add_alternative(body_html, subtype="html", charset="utf-8")
    else:
        msg.set_content(body_text or "", subtype="plain", charset="utf-8")

    for pth in (attachments or []):
        p = Path(pth)
        if not p.exists():
            continue
        ctype, _enc = mimetypes.guess_type(str(p))
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with p.open("rb") as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=p.name)

    with smtplib.SMTP(settings.smtp_host, int(settings.smtp_port or 587), timeout=30) as server:
        server.ehlo(); server.starttls(); server.ehlo()
        server.login(settings.smtp_user, settings.smtp_pass)
        server.send_message(msg)

# --- Resend (primary) ---
RESEND_API_KEY = os.getenv("RESEND_API_KEY") or os.getenv("EMAIL_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", settings.from_email or "")
FROM_NAME  = os.getenv("FROM_NAME", "AI Meeting Notes")
EMAIL_SERVICE = os.getenv("EMAIL_SERVICE", "resend").lower()

def _resend_send(to_email: str, subject: str, body_text: str, body_html: str | None, attachments: list[str] | None):
    if not (EMAIL_SERVICE == "resend" and RESEND_API_KEY and FROM_EMAIL):
        # not configured → try SMTP → then dev outbox
        return _smtp_send(to_email, subject, body_text, body_html, attachments)

    data = {
        "from": f"{FROM_NAME} <{FROM_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        # Resend supports both; send at least one. We include both for safety.
        "text": body_text or "",
        "html": body_html or f"<pre style='white-space:pre-wrap'>{(body_text or '')}</pre>",
    }

    # Optional attachments (inline base64)
    enc_attachments = []
    for pth in (attachments or []):
        p = Path(pth)
        if not p.exists():
            continue
        b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
        enc_attachments.append({"filename": p.name, "content": b64})
    if enc_attachments:
        data["attachments"] = enc_attachments

    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=30) as client:
            r = client.post("https://api.resend.com/emails", headers=headers, json=data)
            if r.status_code != 200:
                # On failure, drop to SMTP, then dev outbox
                _smtp_send(to_email, f"[RESEND FAIL] {subject}",
                           (body_text or "") + f"\n\n[Resend error {r.status_code}] {r.text}",
                           body_html, attachments)
            # else: sent OK
    except Exception as e:
        _smtp_send(to_email, f"[RESEND EXC] {subject}",
                   (body_text or "") + f"\n\n[Resend exception] {e}",
                   body_html, attachments)

# --- Public API ---
def send_email(to_email: str, subject: str, body_text: str, body_html: str | None = None, attachments: list[str] | None = None):
    """
    Primary: Resend (if EMAIL_SERVICE=resend & RESEND_API_KEY present)
    Fallback: SMTP (if configured)
    Fallback: dev outbox file
    """
    _resend_send(to_email, subject, body_text, body_html, attachments)
