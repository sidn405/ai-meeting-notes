# app/services/branding.py
from __future__ import annotations
import os, re, html
from typing import Dict, List, Tuple, Optional
from ..config import get_settings

settings = get_settings()

# Branding via env (safe defaults)
BRAND_NAME          = os.getenv("BRAND_NAME", "LGE Tools")
BRAND_LOGO_URL      = os.getenv("BRAND_LOGO_URL", "")  # e.g., https://yourcdn/logo.png
BRAND_PRIMARY_COLOR = os.getenv("BRAND_PRIMARY_COLOR", "#0D1A2B")   # header/buttons
BRAND_ACCENT_COLOR  = os.getenv("BRAND_ACCENT_COLOR",  "#0ea5e9")   # accents/links
BRAND_FOOTER_TEXT   = os.getenv("BRAND_FOOTER_TEXT",  f"© {BRAND_NAME} • All rights reserved")

def _split_sections(text: str) -> Dict[str, str]:
    """
    Heuristically split meeting notes into known sections.
    Looks for headings like 'Executive Summary', 'Key Decisions', 'Action Items'.
    Falls back to single 'Body' if not found.
    """
    if not text:
        return {"Body": ""}

    # Normalize line endings
    t = text.replace("\r\n", "\n").replace("\r", "\n")

    # Try markdown-style headers
    pattern = r"(?im)^(?:#{1,3}\s*)?(Executive Summary|Key Decisions|Action Items)\s*:?\s*$"
    parts = {}
    last = None
    buf: List[str] = []
    for line in t.split("\n"):
        m = re.match(pattern, line.strip())
        if m:
            if last and buf:
                parts[last] = "\n".join(buf).strip()
                buf = []
            last = m.group(1)
        else:
            buf.append(line)
    if last:
        parts[last] = "\n".join(buf).strip()

    # If nothing matched, try plain keyword splits
    if not parts:
        keys = ["Executive Summary", "Key Decisions", "Action Items"]
        cur = "Body"
        parts[cur] = ""
        for line in t.split("\n"):
            hit = None
            for k in keys:
                if re.match(rf"(?i)^\s*{re.escape(k)}\s*:?\s*$", line.strip()):
                    hit = k; break
            if hit:
                cur = hit
                if cur not in parts: parts[cur] = ""
            else:
                parts[cur] = (parts.get(cur, "") + line + "\n")
        # trim
        for k in list(parts):
            parts[k] = parts[k].strip()

    return parts or {"Body": t.strip()}

def _bullets_to_html(body: str) -> str:
    """
    Convert simple '-' or '*' bullets and '1.' lists into <ul>/<ol>.
    Otherwise escape + <p>.
    """
    if not body:
        return ""
    lines = [l.rstrip() for l in body.split("\n") if l.strip() != ""]
    if not lines:
        return ""

    # Detect list type
    is_ul = all(l.strip().startswith(("-", "*", "•")) for l in lines)
    is_ol = all(re.match(r"^\s*\d+\.", l) for l in lines)

    if is_ul:
        items = "".join(f"<li>{html.escape(re.sub(r'^[-*•]\s*', '', l).strip())}</li>" for l in lines)
        return f"<ul style='margin:0 0 8px 20px'>{items}</ul>"
    if is_ol:
        items = "".join(f"<li>{html.escape(re.sub(r'^\s*\d+\.\s*', '', l).strip())}</li>" for l in lines)
        return f"<ol style='margin:0 0 8px 20px'>{items}</ol>"

    # Fallback preserve formatting
    return "<p style='white-space:pre-wrap;margin:0'>" + html.escape(body) + "</p>"

def _section_block(title: str, content: str) -> str:
    return (
        f"<h3 style='margin:0 0 8px 0;font-size:16px;color:#111'>{html.escape(title)}</h3>"
        f"{_bullets_to_html(content)}"
    )

def _cta_button(href: str, label: str) -> str:
    return (
        f"<a href='{html.escape(href)}' "
        f"style='display:inline-block;background:{BRAND_PRIMARY_COLOR};color:#fff;"
        f"padding:10px 14px;border-radius:8px;text-decoration:none;font-weight:600;margin-right:10px'>"
        f"{html.escape(label)}</a>"
    )

def render_meeting_notes_email_html(
    *,
    meeting_title: str,
    summary_text: str,
    meeting_id: Optional[int] = None,
    include_download_ctas: bool = True,
) -> str:
    """
    Build a branded HTML email for meeting notes.
    If meeting_id is provided, we add download buttons using APP_BASE_URL.
    """
    sections = _split_sections(summary_text)

    # Optional CTAs
    ctas = ""
    if include_download_ctas and meeting_id is not None:
        base = settings.base_url.rstrip("/")
        transcript_url = f"{base}/meetings/{meeting_id}/download/transcript"
        summary_url    = f"{base}/meetings/{meeting_id}/download/summary"
        ctas = _cta_button(summary_url, "Download Summary JSON") + _cta_button(transcript_url, "Download Transcript")

    # Build section HTML
    blocks = []
    order = ["Executive Summary", "Key Decisions", "Action Items", "Body"]
    for key in order:
        if key in sections and sections[key]:
            blocks.append(_section_block(key, sections[key]))
    if not blocks:
        blocks.append(_section_block("Notes", summary_text))

    logo_html = (
        f"<img src='{html.escape(BRAND_LOGO_URL)}' alt='{html.escape(BRAND_NAME)}' "
        f"style='height:28px;display:block' />"
        if BRAND_LOGO_URL else f"<div style='font-weight:800;font-size:18px;color:#fff'>{html.escape(BRAND_NAME)}</div>"
    )

    return f"""\
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="color-scheme" content="light only">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#f6f7f9">
  <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:{BRAND_PRIMARY_COLOR}">
    <tr><td style="padding:16px 20px">
      {logo_html}
    </td></tr>
  </table>

  <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
    <tr><td align="center" style="padding:24px 12px">
      <table role="presentation" cellpadding="0" cellspacing="0" width="640" style="max-width:640px;background:#ffffff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);overflow:hidden">
        <tr><td style="padding:24px 24px 8px 24px">
          <h2 style="margin:0 0 4px 0;font-size:20px;color:#111">Meeting Notes</h2>
          <div style="font-size:14px;color:#555">{html.escape(meeting_title)}</div>
        </td></tr>

        <tr><td style="padding:8px 24px 0 24px">
          {"".join(blocks)}
        </td></tr>

        {"<tr><td style='padding:16px 24px'>" + ctas + "</td></tr>" if ctas else ""}

        <tr><td style="height:8px"></td></tr>
      </table>

      <div style="font-size:12px;color:#6b7280;margin-top:16px">{html.escape(BRAND_FOOTER_TEXT)}</div>
    </td></tr>
  </table>
</body>
</html>
"""

def compose_meeting_email_parts(
    *,
    meeting_title: str,
    summary_text: str,
    meeting_id: Optional[int],
    attach_paths: Optional[List[str]] = None,
) -> Tuple[str, str, str, List[str]]:
    """
    Returns: (subject, plain_text, html, attachments)
    """
    subject = f"Meeting Notes: {meeting_title}"
    # Plain text fallback
    text = f"{BRAND_NAME} — Meeting Notes\n\nTitle: {meeting_title}\n\n{summary_text}\n"
    html_body = render_meeting_notes_email_html(
        meeting_title=meeting_title,
        summary_text=summary_text,
        meeting_id=meeting_id,
        include_download_ctas=True,
    )
    return subject, text, html_body, (attach_paths or [])
