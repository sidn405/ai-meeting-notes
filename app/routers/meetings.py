# app/routers/meetings.py
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Depends, Cookie
from typing import Optional
from ..security import require_auth
from fastapi.responses import FileResponse
from pathlib import Path
from sqlmodel import select
from ..db import get_session, DATA_DIR
from ..models import Meeting
from ..services.pipeline import process_meeting, send_summary_email, process_meeting_transcribe_summarize
import json, re, os

# CHANGED: Import license system
from ..middleware.license import require_license, track_meeting_usage, validate_file_size
from ..services.license import LicenseTier, TIER_LIMITS

router = APIRouter(
    prefix="/meetings",
    tags=["meetings"],
    dependencies=[Depends(require_auth)],
)

def detect_language(audio_path: str) -> str:
    """Auto-detect language if not specified"""
    # If using AssemblyAI, they support auto-detection
    # Just pass language=None or omit it
    return None  # Let AssemblyAI auto-detect

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
    license_info: tuple = Depends(require_license),
    db = Depends(get_session),
):
    """Upload audio/video file and queue for processing"""
    license, tier_config = license_info
    
    # ADDED: Handle empty string for auto-detect
    if language == "":
        language = None  # Triggers auto-detection in transcription
    
    # ADDED: Clean up hints (remove extra whitespace, handle empty)
    if hints:
        hints = hints.strip()
        if not hints:
            hints = None
    
    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".m4a", ".wav", ".mp4"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: .mp3, .m4a, .wav, .mp4")

    # Read file and validate size based on license tier
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    # Check file size against tier limit
    is_valid, error_msg = validate_file_size(file_size, license.tier)
    if not is_valid:
        raise HTTPException(status_code=413, detail=error_msg)
    
    # Save file
    audio_path = DATA_DIR / f"{Path(file.filename).stem}.uploaded{ext}"
    audio_path.write_bytes(file_content)

    # Create meeting record
    with get_session() as s:
        m = Meeting(title=title, audio_path=str(audio_path), email_to=email_to, status="queued")
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Track usage for license
    track_meeting_usage(db, license.license_key)

    # Queue processing
    background_tasks.add_task(
        process_meeting,
        mid,
        language=language,  # Now properly None for auto-detect
        hints=hints
    )
    
    return {
        "id": mid, 
        "status": "queued",
        "tier": license.tier,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "language": language or "auto-detect",  # Show what was selected
    }


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
    license_info: tuple = Depends(require_license),
    db = Depends(get_session),
):
    """Upload and process immediately (blocks until complete)"""
    license, tier_config = license_info
    
    # ADDED: Handle auto-detect
    if language == "":
        language = None
    if hints:
        hints = hints.strip() or None
    
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".m4a", ".wav", ".mp4"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    # Validate file size
    file_content = await file.read()
    file_size = len(file_content)
    
    is_valid, error_msg = validate_file_size(file_size, license.tier)
    if not is_valid:
        raise HTTPException(status_code=413, detail=error_msg)

    audio_path = DATA_DIR / f"{Path(file.filename).stem}.uploaded{ext}"
    audio_path.write_bytes(file_content)

    with get_session() as s:
        m = Meeting(title=title, audio_path=str(audio_path), email_to=email_to, status="queued")
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Track usage
    track_meeting_usage(db, license.license_key)

    # Process synchronously
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
    license_info: tuple = Depends(require_license),  # CHANGED: Add license check
    db = Depends(get_session),
):
    """Create meeting from text transcript (no audio)"""
    license, tier_config = license_info
    
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

    # Track usage
    track_meeting_usage(db, license.license_key)

    # Process meeting
    process_meeting(mid)

    with get_session() as s:
        m = s.get(Meeting, mid)
        return {"id": m.id, "status": m.status}

@router.post("/from-text-sync")
async def create_from_text_sync(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: str | None = Form(None),
    license_info: tuple = Depends(require_license),  # CHANGED: Add license check
    db = Depends(get_session),
):
    """Alias for from-text (already synchronous)"""
    return await create_from_text(title, transcript, email_to, license_info, db)

@router.post("/transcribe-only")
async def transcribe_only(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: str | None = Form(None),
    license_info: tuple = Depends(require_license),
    db = Depends(get_session),
):
    """Save transcript without summarization"""
    license, tier_config = license_info
    
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.strip()) or "meeting"
    tpath = DATA_DIR / f"transcribe_only_{safe_stem}.transcript.txt"
    tpath.write_text(transcript, encoding="utf-8")

    with get_session() as s:
        m = Meeting(
            title=title,
            audio_path=None,
            email_to=email_to,
            transcript_path=str(tpath),
            status="delivered",
            progress=100,
            step="Transcript saved"
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Track usage
    track_meeting_usage(db, license.license_key)

    return {
        "id": mid, 
        "status": "delivered",
        "message": "Transcript saved successfully"
    }

# FULL VERSION - transcribe and summarize
@router.post("/upload-transcribe-summarize")
async def upload_transcribe_summarize(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    email_to: str | None = Form(None),
    file: UploadFile = File(...),
    language: str | None = Form(None),
    hints: str | None = Form(None),
    license_info: tuple = Depends(require_license),
    db = Depends(get_session),
):
    """Upload and transcribe (with summarization)"""
    license, tier_config = license_info
    
    # Handle empty string for auto-detect
    if language == "":
        language = None
    if hints:
        hints = hints.strip() or None
    
    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".m4a", ".wav", ".mp4"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: .mp3, .m4a, .wav, .mp4")

    # Read file and validate size
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    # Check file size against tier limit
    is_valid, error_msg = validate_file_size(file_size, license.tier)
    if not is_valid:
        raise HTTPException(status_code=413, detail=error_msg)
    
    # Save file
    audio_path = DATA_DIR / f"{Path(file.filename).stem}.uploaded{ext}"
    audio_path.write_bytes(file_content)

    # Create meeting record
    with get_session() as s:
        m = Meeting(
            title=title, 
            audio_path=str(audio_path), 
            email_to=email_to, 
            status="queued"
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Track usage
    track_meeting_usage(db, license.license_key)

    # Import the transcribe-only function
    from ..services.pipeline import process_meeting_transcribe_summarize
    
    # Queue transcription (with summarization)
    background_tasks.add_task(
        process_meeting_transcribe_summarize,
        mid,
        language=language,
        hints=hints
    )
    
    return {
        "id": mid, 
        "status": "queued",
        "tier": license.tier,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "language": language or "auto-detect",
        "mode": "transcribe_only"
    }

@router.get("/list")
def list_meetings():
    """Get all meetings ordered by creation date (newest first)"""
    try:
        with get_session() as s:
            meetings = s.exec(
                select(Meeting).order_by(Meeting.created_at.desc())
            ).all()
            return meetings
    except Exception as e:
        print(f"Error fetching meetings: {e}")
        raise HTTPException(500, f"Failed to fetch meetings: {str(e)}")


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


@router.get("/{meeting_id}/status")
def meeting_status(meeting_id: int):
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(404, "Not found")
        return {
            "id": m.id,
            "title": m.title,
            "status": m.status,
            "progress": m.progress or 0,
            "step": m.step,
            "has_summary": bool(m.summary_path),
            "has_transcript": bool(m.transcript_path),
        }


@router.post("/{meeting_id}/run")
def run_meeting(meeting_id: int):
    """Manually trigger processing for a meeting"""
    process_meeting(meeting_id)
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(404, "Not found")
        return {"id": m.id, "status": m.status}

@router.post("/{meeting_id}/summarize")
async def summarize_existing_meeting(
    meeting_id: int,
    background_tasks: BackgroundTasks,
):
    """Summarize an already-transcribed meeting"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(404, "Meeting not found")
        
        if not m.transcript_path or not Path(m.transcript_path).exists():
            raise HTTPException(400, "No transcript available to summarize")
        
        if m.summary_path and Path(m.summary_path).exists():
            raise HTTPException(400, "Meeting already summarized")
    
    # Queue summarization
    #background_tasks.add_task(summarize_existing_transcript, meeting_id)
    
    return {
        "id": meeting_id,
        "status": "processing",
        "message": "Summarization queued"
    }

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


@router.delete("/{meeting_id}")
def delete_meeting(meeting_id: int):
    """Delete a meeting and its associated files"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(status_code=404, detail="Not found")
        
        # Delete associated files
        if m.audio_path and Path(m.audio_path).exists():
            Path(m.audio_path).unlink()
        if m.transcript_path and Path(m.transcript_path).exists():
            Path(m.transcript_path).unlink()
        if m.summary_path and Path(m.summary_path).exists():
            Path(m.summary_path).unlink()
        
        # Delete from database
        s.delete(m)
        s.commit()
        
        return {"success": True, "message": "Meeting deleted"}