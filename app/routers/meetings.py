# app/routers/meetings.py
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Depends, Header
from typing import Optional
from fastapi.responses import FileResponse
from pathlib import Path
from sqlmodel import select, Session
from ..db import get_session, DATA_DIR
from ..models import Meeting, License, LicenseTier, TIER_LIMITS
from ..services.pipeline import process_meeting, send_summary_email, process_meeting_transcribe_summarize, process_meeting_transcribe_only

import json, re

router = APIRouter(
    prefix="/meetings",
    tags=["meetings"],
)

def optional_license(
    x_license_key: str | None = Header(None, alias="X-License-Key"),
    db: Session = Depends(get_session)
):
    """
    Optional license check - returns tier config
    If no license provided, returns FREE tier config
    """
    from app.services.license import validate_license, TIER_LIMITS, LicenseTier
    
    if not x_license_key:
        # No license = FREE tier
        return None, TIER_LIMITS[LicenseTier.FREE.value]
    
    # Validate license if provided
    is_valid, license, error = validate_license(db, x_license_key)
    
    if not is_valid:
        # Invalid license = still allow as FREE tier (don't block)
        return None, TIER_LIMITS[LicenseTier.FREE.value]
    
    tier_config = TIER_LIMITS[license.tier]
    return license, tier_config

def track_meeting_usage(db: Session, license_key: str):
    """
    Check quota and increment usage
    Raises HTTPException if limit reached
    """
    from app.services.license import check_usage_limit, increment_usage
    
    license = db.exec(
        select(License).where(License.license_key == license_key)
    ).first()
    
    if not license:
        raise HTTPException(404, "License not found")
    
    has_quota, used, limit = check_usage_limit(db, license_key, license.tier)
    
    if not has_quota:
        raise HTTPException(
            429,
            f"Monthly meeting limit reached ({used}/{limit}). "
            f"Upgrade your plan for more meetings."
        )
    
    increment_usage(db, license_key)

def validate_file_size(file_size: int, tier_config: dict) -> tuple[bool, str]:
    """Validate file size against tier limits"""
    max_size_mb = tier_config.get("max_file_size_mb", 25)
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if file_size > max_size_bytes:
        return False, f"File size ({file_size / (1024*1024):.1f}MB) exceeds tier limit of {max_size_mb}MB"
    
    return True, ""


@router.post("/upload")
async def upload_meeting(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    email_to: str | None = Form(None),
    file: UploadFile = File(...),
    language: str | None = Form(None),
    hints: str | None = Form(None),
    license_info: tuple = Depends(optional_license),  # ✅ CHANGED
    db = Depends(get_session),
):
    """Upload - works for FREE and PAID users"""
    license, tier_config = license_info
    
    # Handle empty string for auto-detect
    if language == "":
        language = None
    
    # Clean up hints
    if hints:
        hints = hints.strip()
        if not hints:
            hints = None
    
    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".m4a", ".wav", ".mp4", ".mov", ".mkv", ".webm"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    # Read file and validate size
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    # Check file size against tier limit
    is_valid, error_msg = validate_file_size(file_size, tier_config)
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

    # Track usage for paid users only
    if license:  # ✅ ADDED CHECK
        track_meeting_usage(db, license.license_key)

    # Queue processing
    background_tasks.add_task(
        process_meeting,
        mid,
        language=language,
        hints=hints
    )
    
    return {
        "id": mid, 
        "status": "queued",
        "tier": license.tier if license else "free",
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "language": language or "auto-detect",
    }


@router.post("/from-text")
async def create_from_text(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: str | None = Form(None),
    license_info: tuple = Depends(optional_license),  # ✅ CHANGED
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

    # Track usage for paid users only
    if license:  # ✅ ADDED CHECK
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
    license_info: tuple = Depends(optional_license),  # ✅ CHANGED
    db = Depends(get_session),
):
    """Alias for from-text (already synchronous)"""
    return await create_from_text(title, transcript, email_to, license_info, db)


@router.post("/transcribe-only")
async def transcribe_only(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: str | None = Form(None),
    license_info: tuple = Depends(optional_license),  # ✅ CHANGED
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

    # Track usage for paid users only
    if license:  # ✅ ADDED CHECK
        track_meeting_usage(db, license.license_key)

    return {
        "id": mid, 
        "status": "delivered",
        "message": "Transcript saved successfully"
    }


@router.post("/upload-transcribe-only")
async def upload_transcribe_only(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    email_to: str | None = Form(None),
    file: UploadFile = File(...),
    language: str | None = Form(None),
    hints: str | None = Form(None),
    license_info: tuple = Depends(optional_license),  # ✅ CHANGED
    db = Depends(get_session),
):
    """Upload and transcribe ONLY (no summarization)"""
    license, tier_config = license_info
    
    if language == "":
        language = None
    if hints:
        hints = hints.strip() or None
    
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".m4a", ".wav", ".mp4", ".mov", ".mkv", ".webm"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    is_valid, error_msg = validate_file_size(file_size, tier_config)
    if not is_valid:
        raise HTTPException(status_code=413, detail=error_msg)
    
    audio_path = DATA_DIR / f"{Path(file.filename).stem}.uploaded{ext}"
    audio_path.write_bytes(file_content)

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

    # Track usage for paid users only
    if license:  # ✅ ADDED CHECK
        track_meeting_usage(db, license.license_key)

    background_tasks.add_task(
        process_meeting_transcribe_only,
        mid,
        language=language,
        hints=hints
    )
    
    return {
        "id": mid, 
        "status": "queued",
        "tier": license.tier if license else "free",
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "language": language or "auto-detect",
        "mode": "transcribe_only"
    }


@router.post("/upload-transcribe-summarize")
async def upload_transcribe_summarize(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    email_to: str | None = Form(None),
    file: UploadFile = File(...),
    language: str | None = Form(None),
    hints: str | None = Form(None),
    license_info: tuple = Depends(optional_license),  # ✅ CHANGED
    db = Depends(get_session),
):
    """Upload and transcribe (with summarization)"""
    license, tier_config = license_info
    
    if language == "":
        language = None
    if hints:
        hints = hints.strip() or None
    
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".m4a", ".wav", ".mp4", ".mov", ".mkv", ".webm"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    is_valid, error_msg = validate_file_size(file_size, tier_config)
    if not is_valid:
        raise HTTPException(status_code=413, detail=error_msg)
    
    audio_path = DATA_DIR / f"{Path(file.filename).stem}.uploaded{ext}"
    audio_path.write_bytes(file_content)

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

    # Track usage for paid users only
    if license:  # ✅ ADDED CHECK
        track_meeting_usage(db, license.license_key)

    background_tasks.add_task(
        process_meeting_transcribe_summarize,
        mid,
        language=language,
        hints=hints
    )
    
    return {
        "id": mid, 
        "status": "queued",
        "tier": license.tier if license else "free",
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "language": language or "auto-detect",
        "mode": "transcribe_and_summarize"
    }


@router.post("/create-from-url")
async def create_from_url(
    background_tasks: BackgroundTasks,
    payload: dict,
    license_info: tuple = Depends(optional_license),  # ✅ CHANGED
    db = Depends(get_session),
):
    """Create meeting from S3 URL (for multipart uploads)"""
    license, tier_config = license_info
    
    title = payload.get('title')
    file_url = payload.get('file_url')
    filename = payload.get('filename')
    email_to = payload.get('email_to')
    language = payload.get('language')
    hints = payload.get('hints')
    
    if not file_url or not filename:
        raise HTTPException(400, "file_url and filename required")
    
    # Download file from S3 to local storage
    import requests
    response = requests.get(file_url, timeout=300)
    if response.status_code != 200:
        raise HTTPException(400, "Failed to download file from S3")
    
    file_content = response.content
    file_size = len(file_content)
    
    is_valid, error_msg = validate_file_size(file_size, tier_config)
    if not is_valid:
        raise HTTPException(status_code=413, detail=error_msg)
    
    ext = Path(filename).suffix.lower()
    audio_path = DATA_DIR / f"{Path(filename).stem}.uploaded{ext}"
    audio_path.write_bytes(file_content)
    
    with get_session() as s:
        m = Meeting(
            title=title or 'Untitled Meeting',
            audio_path=str(audio_path),
            email_to=email_to,
            status="queued"
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id
    
    # Track usage for paid users only
    if license:  # ✅ ADDED CHECK
        track_meeting_usage(db, license.license_key)
    
    background_tasks.add_task(
        process_meeting_transcribe_summarize,
        mid,
        language=language,
        hints=hints
    )
    
    return {
        "id": mid,
        "status": "queued",
        "file_size_mb": round(file_size / (1024 * 1024), 2),
    }


@router.post("/create-from-url-transcribe-only")
async def create_from_url_transcribe_only(
    background_tasks: BackgroundTasks,
    payload: dict,
    license_info: tuple = Depends(optional_license),  # ✅ CHANGED
    db = Depends(get_session),
):
    """Create meeting from S3 URL - transcribe only"""
    license, tier_config = license_info
    
    title = payload.get('title')
    file_url = payload.get('file_url')
    filename = payload.get('filename')
    email_to = payload.get('email_to')
    language = payload.get('language')
    hints = payload.get('hints')
    
    if not file_url or not filename:
        raise HTTPException(400, "file_url and filename required")
    
    import requests
    response = requests.get(file_url, timeout=300)
    if response.status_code != 200:
        raise HTTPException(400, "Failed to download file from S3")
    
    file_content = response.content
    file_size = len(file_content)
    
    is_valid, error_msg = validate_file_size(file_size, tier_config)
    if not is_valid:
        raise HTTPException(status_code=413, detail=error_msg)
    
    ext = Path(filename).suffix.lower()
    audio_path = DATA_DIR / f"{Path(filename).stem}.uploaded{ext}"
    audio_path.write_bytes(file_content)
    
    with get_session() as s:
        m = Meeting(
            title=title or 'Untitled Meeting',
            audio_path=str(audio_path),
            email_to=email_to,
            status="queued"
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id
    
    # Track usage for paid users only
    if license:  # ✅ ADDED CHECK
        track_meeting_usage(db, license.license_key)
    
    background_tasks.add_task(
        process_meeting_transcribe_only,
        mid,
        language=language,
        hints=hints
    )
    
    return {
        "id": mid,
        "status": "queued",
        "file_size_mb": round(file_size / (1024 * 1024), 2),
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
        
        s.delete(m)
        s.commit()
        
        return {"success": True, "message": "Meeting deleted"}