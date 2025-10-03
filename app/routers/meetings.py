# app/routers/meetings.py
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Depends
from typing import Optional
from ..security import require_auth
from fastapi.responses import FileResponse
from pathlib import Path
from sqlmodel import select
from ..db import get_session, DATA_DIR
from ..models import Meeting
from ..services.pipeline import process_meeting, send_summary_email
import json, re

router = APIRouter(
    prefix="/meetings",
    tags=["meetings"],
    dependencies=[Depends(require_auth)],
)

def _truthy(v) -> bool:
    """Helper to check if form value is truthy"""
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


@router.post("/upload")
async def upload_meeting(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    email_to: str | None = Form(None),
    file: UploadFile = File(...),
    language: str | None = Form(None),
    hints: str | None = Form(None),
    model_size: str | None = Form(None),
    device: str | None = Form(None),
    compute_type: str | None = Form(None),
):
    """Upload audio/video file and queue for processing"""
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".m4a", ".wav", ".mp4"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    audio_path = DATA_DIR / f"{Path(file.filename).stem}.uploaded{ext}"
    audio_path.write_bytes(await file.read())

    with get_session() as s:
        m = Meeting(title=title, audio_path=str(audio_path), email_to=email_to, status="queued")
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Queue the processing using pipeline's process_meeting
    background_tasks.add_task(
        process_meeting,
        mid,
        language=language,
        hints=hints
    )
    
    return {"id": mid, "status": "queued"}


@router.post("/upload-sync")
async def upload_meeting_sync(
    title: str = Form(...),
    email_to: str | None = Form(None),
    file: UploadFile = File(...),
    language: str | None = Form(None),
    hints: str | None = Form(None),
    model_size: str | None = Form(None),
    device: str | None = Form(None),
    compute_type: str | None = Form(None),
):
    """Upload and process immediately (blocks until complete)"""
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".m4a", ".wav", ".mp4"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    audio_path = DATA_DIR / f"{Path(file.filename).stem}.uploaded{ext}"
    audio_path.write_bytes(await file.read())

    with get_session() as s:
        m = Meeting(title=title, audio_path=str(audio_path), email_to=email_to, status="queued")
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Process immediately and wait
    process_meeting(mid, language=language, hints=hints)

    with get_session() as s:
        m = s.get(Meeting, mid)
        if not m:
            raise HTTPException(404, "Not found")
        return {"id": m.id, "status": m.status}


@router.post("/from-text")
async def create_from_text(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: str | None = Form(None),
):
    """Create meeting from text transcript (no audio)"""
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.strip()) or "meeting"
    tpath = DATA_DIR / f"from_text_{safe_stem}.transcript.txt"
    tpath.write_text(transcript, encoding="utf-8")

    with get_session() as s:
        m = Meeting(
            title=title,
            audio_path=None,
            email_to=email_to,
            transcript_path=str(tpath),
            status="queued"
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Process immediately (text-only is fast)
    process_meeting(mid)

    with get_session() as s:
        m = s.get(Meeting, mid)
        return {"id": m.id, "status": m.status}


@router.post("/from-text-sync")
async def create_from_text_sync(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: str | None = Form(None),
):
    """Alias for from-text (already synchronous)"""
    return await create_from_text(title, transcript, email_to)


@router.get("/{meeting_id}")
def get_meeting(meeting_id: int):
    """Get meeting details"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(status_code=404, detail="Not found")
        return m


@router.get("/{meeting_id}/download/transcript")
def download_transcript(meeting_id: int):
    """Download meeting transcript"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not (m and m.transcript_path and Path(m.transcript_path).exists()):
            raise HTTPException(status_code=404, detail="Transcript not found")
        return FileResponse(
            m.transcript_path,
            media_type="text/plain",
            filename=Path(m.transcript_path).name
        )


@router.get("/{meeting_id}/download/summary")
def download_summary(meeting_id: int):
    """Download meeting summary (as file attachment)"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not (m and m.summary_path and Path(m.summary_path).exists()):
            raise HTTPException(status_code=404, detail="Summary not found")
        return FileResponse(
            m.summary_path,
            media_type="application/json",
            filename=Path(m.summary_path).name
        )


@router.get("/{meeting_id}/summary")
def get_summary(meeting_id: int):
    """Get meeting summary as JSON (for reading, not downloading)"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not (m and m.summary_path and Path(m.summary_path).exists()):
            raise HTTPException(status_code=404, detail="Summary not found")
        
        summary_text = Path(m.summary_path).read_text(encoding="utf-8")
        return json.loads(summary_text)


@router.post("/{meeting_id}/run")
def run_meeting(meeting_id: int):
    """Manually trigger processing for a meeting"""
    process_meeting(meeting_id)
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(404, "Not found")
        return {"id": m.id, "status": m.status}


@router.post("/{meeting_id}/send-email")
async def send_meeting_email(meeting_id: int, payload: dict):
    """Send or resend meeting summary via email"""
    email_to = payload.get("email_to")
    if not email_to:
        raise HTTPException(400, "email_to is required")
    
    try:
        send_summary_email(meeting_id, email_to)
        return {"success": True, "message": f"Email sent to {email_to}"}
    except Exception as e:
        raise HTTPException(500, f"Failed to send email: {str(e)}")