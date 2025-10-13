# app/services/pipeline.py
from __future__ import annotations
import re
import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx
from openai import OpenAI
from sqlmodel import select
from sqlalchemy import text as sql_text

from ..db import get_session, DATA_DIR
from ..models import Meeting
from ..utils.storage import save_text

# ---------- ASR (AssemblyAI) ----------

def _aai_upload(local_path: str, api_key: str) -> str:
    """
    Uploads a local file to AssemblyAI and returns a temporary URL.
    """
    headers = {"authorization": api_key}
    url = "https://api.assemblyai.com/v2/upload"

    def _iter_chunks(fp, chunk_size=5 * 1024 * 1024):
        while True:
            data = fp.read(chunk_size)
            if not data:
                break
            yield data

    with open(local_path, "rb") as f:
        r = httpx.post(url, headers=headers, content=_iter_chunks(f), timeout=None)
    r.raise_for_status()
    # API returns {"upload_url": "..."} (older responses may use "url")
    j = r.json()
    return j.get("upload_url") or j.get("url")

def _aai_transcribe(audio_path: str, *, language: Optional[str], hints: Optional[str]) -> str:
    """
    Create/poll a transcription job and return the transcript text.
    """
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise RuntimeError("ASSEMBLYAI_API_KEY is not set")

    audio_url = _aai_upload(audio_path, api_key)

    payload: dict = {"audio_url": audio_url}
    if language:
        payload["language_code"] = language.strip()

    if hints:
        # Accept comma/newline separated terms
        wb = [w.strip() for w in hints.replace("\n", ",").split(",") if w.strip()]
        if wb:
            payload["word_boost"] = wb
            payload["boost_param"] = "high"

    headers = {"authorization": api_key, "content-type": "application/json"}
    create = httpx.post(
        "https://api.assemblyai.com/v2/transcript",
        headers=headers,
        json=payload,
        timeout=None,
    )
    create.raise_for_status()
    tid = create.json()["id"]

    # Poll until done
    while True:
        res = httpx.get(f"https://api.assemblyai.com/v2/transcript/{tid}", headers=headers, timeout=None)
        res.raise_for_status()
        j = res.json()
        status = j.get("status")
        if status == "completed":
            return j.get("text", "")
        if status == "error":
            raise RuntimeError(f"AssemblyAI error: {j.get('error')}")
        time.sleep(3)

# ---------- LLM summary (OpenAI) ----------

def _summarize_with_openai(transcript: str, title: str) -> dict:
    """
    Return a JSON structure with executive_summary, key_decisions, action_items.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    sys = (
        "You produce concise business meeting notes in JSON. "
        "Fields: executive_summary (string), key_decisions (array of strings), "
        "action_items (array of objects with owner, task, due_date [YYYY-MM-DD or empty], priority [High/Medium/Low]). "
        "Be faithful to the transcript; do not invent details."
    )
    user = f"Title: {title}\n\nTranscript:\n{transcript}"

    resp = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
        temperature=0.2,
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)

# ---------- Email (Resend) ----------

def _email_with_resend_by_id(meeting_id: int, summary_json: dict, summary_path: str, override_to: str):
    """Send the formatted email using Resend. No-op if config isn't present."""
    service = os.getenv("EMAIL_SERVICE", "resend").lower()
    if service != "resend":
        return

    api = os.getenv("EMAIL_API_KEY")
    from_email = os.getenv("FROM_EMAIL")
    from_name = os.getenv("FROM_NAME", "AI Meeting Notes")
    
    if not api or not from_email or not override_to:
        return

    # Get meeting title from database in a new session
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            return
        meeting_title = m.title

    app_base = os.getenv("APP_BASE_URL", "").rstrip("/")
    links = ""
    if app_base:
        links = (
            f'<p><a href="{app_base}/meetings/{meeting_id}/download/summary">Download summary (JSON)</a> · '
            f'<a href="{app_base}/meetings/{meeting_id}/download/transcript">Download transcript (TXT)</a></p>'
        )

    ex = summary_json.get("executive_summary", "") or ""
    dec = summary_json.get("key_decisions", []) or []
    ai  = summary_json.get("action_items", []) or []

    rows = ""
    for it in ai:
        rows += f"<tr><td>{it.get('owner','')}</td><td>{it.get('task','')}</td><td>{it.get('due_date','')}</td><td>{it.get('priority','')}</td></tr>"

    html = f"""
    <h3>Executive Summary</h3>
    <p style="white-space:pre-wrap">{ex}</p>
    <h3>Key Decisions</h3>
    <ul>{"".join(f"<li>{d}</li>" for d in dec)}</ul>
    <h3>Action Items</h3>
    <table border="1" cellpadding="6" cellspacing="0">
      <tr><th>Owner</th><th>Task</th><th>Due Date</th><th>Priority</th></tr>
      {rows}
    </table>
    {links}
    """

    r = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api}", "Content-Type": "application/json"},
        json={
            "from": f"{from_name} <{from_email}>",
            "to": [override_to],
            "subject": f"Meeting Notes: {meeting_title}",
            "html": html,
        },
        timeout=30,
    )
    r.raise_for_status()
    
def send_summary_email(meeting_id: int, to: str):
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m or not m.summary_path or not Path(m.summary_path).exists():
            raise RuntimeError("Summary not ready")
        summary_path = m.summary_path  # Store path before session closes
    
    summary_json = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    _email_with_resend_by_id(meeting_id, summary_json, summary_path, override_to=to)  # ✅ Pass meeting_id, not m

# ---------- Main pipeline ----------

def _set_progress(meeting_id: int, progress: int, *, step: str | None = None, status: str | None = None):
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            return
        m.progress = max(0, min(progress, 100))
        if step is not None:
            m.step = step
        if status is not None:
            m.status = status
        s.add(m)
        s.commit()

def process_meeting(meeting_id: int, *, language: str | None = None, hints: str | None = None) -> None:
    # mark processing
    _set_progress(meeting_id, 5, step="Starting", status="processing")

    # Get initial meeting data
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise RuntimeError(f"Meeting {meeting_id} not found")
        
        # Store data we'll need later (before session closes)
        meeting_title = m.title
        audio_path = m.audio_path
        transcript_path = m.transcript_path
        email_to = m.email_to

    try:
        transcript_text = ""
        if transcript_path and Path(transcript_path).exists():
            _set_progress(meeting_id, 10, step="Reading transcript")
            transcript_text = Path(transcript_path).read_text(encoding="utf-8")
        elif audio_path and Path(audio_path).exists():
            _set_progress(meeting_id, 20, step="Uploading audio")
            transcript_text = _aai_transcribe(audio_path, language=language, hints=hints)
            _set_progress(meeting_id, 60, step="Transcription complete, saving transcript")
            tpath = save_text(transcript_text, title=meeting_title)
            with get_session() as s:
                mm = s.get(Meeting, meeting_id)
                mm.transcript_path = tpath
                s.add(mm)
                s.commit()
                transcript_path = tpath
        else:
            raise RuntimeError("No transcript or audio found.")

        _set_progress(meeting_id, 75, step="Summarizing")
        summary_json = _summarize_with_openai(transcript_text, meeting_title)

        base_dir = Path(transcript_path).parent if transcript_path else (DATA_DIR / "summaries")
        base_dir.mkdir(parents=True, exist_ok=True)
        spath = str((base_dir / f"summary_{meeting_id}.json").resolve())
        Path(spath).write_text(json.dumps(summary_json, indent=2), encoding="utf-8")

        with get_session() as s:
            mm = s.get(Meeting, meeting_id)
            mm.summary_path = spath
            s.add(mm)
            s.commit()

        _set_progress(meeting_id, 90, step="Emailing (if configured)")
        
        # Email using stored data, not the detached object
        if email_to:
            _email_with_resend_by_id(meeting_id, summary_json, spath, email_to)

        _set_progress(meeting_id, 100, step="Done", status="delivered")

    except Exception as e:
        _set_progress(meeting_id, 100, step=f"Error: {str(e)}", status="failed")
        raise

#  ---------- Transcription code ----------

def process_meeting_transcribe_only(meeting_id: int, *, language: str | None = None, hints: str | None = None) -> None:
    """
    Process meeting for transcription only (no summarization).
    Similar to process_meeting but stops after transcription.
    """
    # Mark processing
    _set_progress(meeting_id, 5, step="Starting transcription", status="processing")

    # Get initial meeting data
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise RuntimeError(f"Meeting {meeting_id} not found")
        
        # Store data we'll need later (before session closes)
        meeting_title = m.title
        audio_path = m.audio_path
        transcript_path = m.transcript_path

    try:
        transcript_text = ""
        
        # If transcript already exists, just mark as complete
        if transcript_path and Path(transcript_path).exists():
            _set_progress(meeting_id, 100, step="Transcript already exists", status="delivered")
            return
        
        # If audio file exists, transcribe it
        elif audio_path and Path(audio_path).exists():
            _set_progress(meeting_id, 20, step="Uploading audio to AssemblyAI")
            transcript_text = _aai_transcribe(audio_path, language=language, hints=hints)
            
            _set_progress(meeting_id, 90, step="Saving transcript")
            
            # Save transcript
            tpath = save_text(transcript_text, title=meeting_title)
            
            # Update database with transcript path
            with get_session() as s:
                mm = s.get(Meeting, meeting_id)
                mm.transcript_path = tpath
                s.add(mm)
                s.commit()
            
            _set_progress(meeting_id, 100, step="Transcription complete", status="delivered")
        else:
            raise RuntimeError("No audio file found for transcription.")

    except Exception as e:
        _set_progress(meeting_id, 100, step=f"Transcription failed: {str(e)}", status="failed")
        print(f"Transcription failed for meeting {meeting_id}: {e}")
        raise