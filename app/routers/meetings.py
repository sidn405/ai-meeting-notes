# app/routers/meetings.py
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Depends, Header, Query
from typing import Optional
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path
from sqlmodel import select, Session
from ..db import get_session, DATA_DIR
from ..models import Meeting, License, LicenseTier, TIER_LIMITS
from ..services.pipeline import process_meeting, send_summary_email, process_meeting_transcribe_summarize, process_meeting_transcribe_only

import json, re, os

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

# Add this function alongside optional_license in meetings.py

def require_license(
    x_license_key: str = Header(..., alias="X-License-Key"),  # Required, not optional
    db: Session = Depends(get_session)
):
    """
    Required license check - blocks users without valid license
    Use this for premium features like cloud storage
    """
    from app.services.license import validate_license, TIER_LIMITS
    
    if not x_license_key:
        raise HTTPException(
            status_code=401,
            detail="No license key found. Please activate your license at /activate"
        )
    
    # Validate license
    is_valid, license, error = validate_license(db, x_license_key)
    
    if not is_valid:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid license: {error}"
        )
    
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


# UPDATE the existing upload endpoint to support video
@router.post("/upload")
async def upload_meeting(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    email_to: str | None = Form(None),
    file: UploadFile = File(...),
    language: str | None = Form(None),
    hints: str | None = Form(None),
    file_type: str = Form("audio"),  # "audio" or "video"
    license_info: tuple = Depends(optional_license),
    db = Depends(get_session),
):
    """
    Upload - ALL TIERS can upload audio/video files
    
    Important distinction:
    - File upload (audio/video): ALL tiers ✅
    - Live video recording: Business tier only (UI feature) 🎥
    
    Free/Starter: Content auto-saved to device after processing
    Pro/Business: Content stored permanently in B2 cloud
    """
    license, tier_config = license_info
    tier = license.tier.lower() if license else "free"
    
    # Handle empty string for auto-detect
    if language == "":
        language = None
    
    # Clean up hints
    if hints:
        hints = hints.strip()
        if not hints:
            hints = None
    
    # Validate file type - ALL TIERS support audio and video files
    ext = Path(file.filename).suffix.lower()
    
    # Audio extensions
    audio_exts = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}
    # Video extensions  
    video_exts = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
    
    all_supported = audio_exts | video_exts
    
    if ext not in all_supported:
        raise HTTPException(400, f"Unsupported file type: {ext}. Supported: audio (mp3, m4a, wav, etc.) and video (mp4, mov, etc.)")
    
    # Determine file type from extension if not specified
    if ext in audio_exts:
        detected_type = "audio"
    elif ext in video_exts:
        detected_type = "video"
    else:
        detected_type = file_type
    
    # Read file and validate size
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    # Check file size against tier limit
    is_valid, error_msg = validate_file_size(file_size, tier_config)
    if not is_valid:
        raise HTTPException(status_code=413, detail=error_msg)
    
    # Save file to temp directory
    temp_dir = DATA_DIR / "temp_media"
    temp_dir.mkdir(exist_ok=True, parents=True)
    
    media_path = temp_dir / f"{Path(file.filename).stem}.uploaded{ext}"
    media_path.write_bytes(file_content)

    # Create meeting record using the existing db session
    m = Meeting(
        title=title,
        audio_path=str(media_path),
        email_to=email_to,
        status="queued",
        media_type=detected_type,
        license_id=license.id if license else None 
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    mid = m.id

    # Track usage for paid users only
    if license:
        track_meeting_usage(db, license.license_key)

    # Queue processing
    background_tasks.add_task(
        process_meeting,
        mid,
        language=language,
        hints=hints
    )
    
    retention_note = ""
    response_data = {
        "id": mid, 
        "status": "queued",
        "tier": tier,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "file_type": detected_type,
    }

    if tier in ("free", "starter"):
        retention_note = "Will be saved to your device automatically after processing. Not stored on server."
        response_data["auto_download_required"] = True
        response_data["storage_location"] = "device"
    else:
        retention_note = "Stored permanently in cloud after processing."
        response_data["auto_download_required"] = False
        response_data["storage_location"] = "cloud"

    response_data["retention"] = retention_note
    return response_data
    
@router.get("/stats")
def get_meeting_stats(
    license_info: tuple = Depends(optional_license),
    db: Session = Depends(get_session),
):
    """
    Get meeting statistics for the current user
    Returns counts of total, completed, processing, and current month meetings
    """
    license, tier_config = license_info
    
    # For now, return global stats (in production, filter by user/license)
    from datetime import datetime
    from sqlmodel import func
    
    total_meetings = db.exec(
        select(func.count(Meeting.id))
    ).one()
    
    completed_meetings = db.exec(
        select(func.count(Meeting.id)).where(Meeting.status == "delivered")
    ).one()
    
    processing_meetings = db.exec(
        select(func.count(Meeting.id)).where(
            (Meeting.status == "processing") | (Meeting.status == "queued")
        )
    ).one()
    
    # Meetings this month
    now = datetime.now()
    first_day_of_month = datetime(now.year, now.month, 1)
    
    meetings_this_month = db.exec(
        select(func.count(Meeting.id)).where(
            Meeting.created_at >= first_day_of_month
        )
    ).one()
    
    return {
        "total_meetings": total_meetings,
        "completed": completed_meetings,
        "processing": processing_meetings,
        "meetings_this_month": meetings_this_month,
        "current_month": now.strftime("%B %Y"),
    }
    
@router.get("/list")
def list_meetings(db: Session = Depends(get_session)):
    """Get all meetings ordered by creation date (newest first) with storage info"""
    try:
        meetings = db.exec(
            select(Meeting).order_by(Meeting.created_at.desc())
        ).all()
        
        # Add storage info to each meeting
        result = []
        for m in meetings:
            transcript_in_cloud = m.transcript_path and m.transcript_path.startswith("s3://")
            summary_in_cloud = m.summary_path and m.summary_path.startswith("s3://")
            
            meeting_dict = {
                "id": m.id,
                "title": m.title,
                "status": m.status,
                "progress": m.progress or 0,
                "step": m.step,
                "has_summary": bool(m.summary_path),
                "has_transcript": bool(m.transcript_path),
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "storage_location": "cloud" if (transcript_in_cloud or summary_in_cloud) else "local",
                "transcript_in_cloud": transcript_in_cloud,
                "summary_in_cloud": summary_in_cloud,
                "media_type": m.media_type if hasattr(m, 'media_type') else "audio",
            }
            result.append(meeting_dict)
        
        return result
    except Exception as e:
        print(f"Error fetching meetings: {e}")
        raise HTTPException(500, f"Failed to fetch meetings: {str(e)}")
    
@router.get("/{meeting_id}/status")
def meeting_status(meeting_id: int, db: Session = Depends(get_session)):
    """Get meeting status with cloud storage info"""
    m = db.get(Meeting, meeting_id)
    if not m:
        raise HTTPException(404, "Not found")
    
    # Check if files are in cloud
    transcript_in_cloud = m.transcript_path and m.transcript_path.startswith("s3://")
    summary_in_cloud = m.summary_path and m.summary_path.startswith("s3://")
    
    return {
        "id": m.id,
        "title": m.title,
        "status": m.status,
        "progress": m.progress or 0,
        "step": m.step,
        "has_summary": bool(m.summary_path),
        "has_transcript": bool(m.transcript_path),
        "storage_location": "cloud" if (transcript_in_cloud or summary_in_cloud) else "local",
        "transcript_in_cloud": transcript_in_cloud,
        "summary_in_cloud": summary_in_cloud,
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
    
# Add these endpoints to your meetings.py file

@router.get("/{meeting_id}/transcript")
def get_transcript(meeting_id: int):
    """Get meeting transcript as JSON (for reading, not downloading)"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if not (m.transcript_path and Path(m.transcript_path).exists()):
            raise HTTPException(status_code=404, detail="Transcript not found")
        
        transcript_text = Path(m.transcript_path).read_text(encoding="utf-8")
        
        return {
            "transcript": transcript_text,
            "title": m.title,
            "meeting_id": m.id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }

@router.post("/email")
async def email_meeting(
    payload: dict,
    db: Session = Depends(get_session),
):
    """
    Email meeting content (transcript and/or summary) to a specified address
    
    Expected payload:
    {
        "meeting_id": int,
        "email": str
        
    }
    """
    meeting_id = payload.get('meeting_id')
    email = payload.get('email')
    
    
    if not meeting_id or not email:
        raise HTTPException(400, "meeting_id and email are required")
    
    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise HTTPException(400, "Invalid email format")
    
    # Get meeting
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    
    # Check if meeting has transcript or summary
    has_transcript = meeting.transcript_path and Path(meeting.transcript_path).exists()
    has_summary = meeting.summary_path and Path(meeting.summary_path).exists()
    
    if not has_transcript and not has_summary:
        raise HTTPException(404, "Meeting has no transcript or summary. Ensure the meeting has been processed.")
    
    # Send email directly (not queued) with correct parameter order
    try:
        # Fix parameter order: meeting_id, email_to, summary_path (or transcript_path if no summary)
        file_path = meeting.summary_path if has_summary else meeting.transcript_path
        send_summary_email(meeting_id, email, file_path)
        
        return {
            "success": True,
            "message": f"Email sent to {email}",
            "meeting_id": meeting_id
        }
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        raise HTTPException(500, f"Failed to send email: {str(e)}")

# UPDATE the existing download endpoint to handle tier-based logic
@router.get("/{meeting_id}/download")
def download_meeting_file(
    meeting_id: int,
    type: str = Query(..., description="transcript, summary, or pdf"),
    license_info: tuple = Depends(optional_license),
    db: Session = Depends(get_session)
):
    """Download meeting files - from B2 for Pro/Business, from server for Free/Starter"""
    license, tier_config = license_info
    tier = license.tier.lower() if license else "free"
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    
    # Verify ownership - check if meeting belongs to this license
    if license:
        # User has a license - verify they own this meeting
        if meeting.license_id != license.id:
            raise HTTPException(403, "Not authorized")
    else:
        # No license provided - only allow if meeting has no license (legacy/free)
        if meeting.license_id is not None:
            raise HTTPException(403, "License required to access this meeting")
    
    try:
        if type == "transcript":
            file_path = meeting.transcript_path
            if not file_path:
                raise HTTPException(404, "Transcript not found")
            
            # Pro/Business - Generate B2 presigned URL
            if file_path.startswith("s3://"):
                from app.routers.storage_b2 import s3_client, get_bucket
                
                s3 = s3_client()
                bucket = get_bucket()
                key = file_path.replace(f"s3://{bucket}/", "")
                
                # Generate presigned URL (valid for 1 hour)
                download_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': key},
                    ExpiresIn=3600
                )
                
                return {
                    "download_url": download_url,
                    "filename": f"meeting_{meeting_id}_transcript.txt",
                    "storage": "cloud"
                }
            
            # Free/Starter - Local file
            else:
                if not Path(file_path).exists():
                    raise HTTPException(404, "Transcript file not found on server")
                
                return FileResponse(
                    file_path,
                    media_type="text/plain",
                    filename=f"meeting_{meeting_id}_transcript.txt"
                )
        
        elif type == "summary":
            file_path = meeting.summary_path
            if not file_path:
                raise HTTPException(404, "Summary not found")
            
            # Pro/Business - Generate B2 presigned URL
            if file_path.startswith("s3://"):
                from app.routers.storage_b2 import s3_client, get_bucket
                
                s3 = s3_client()
                bucket = get_bucket()
                key = file_path.replace(f"s3://{bucket}/", "")
                
                download_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': key},
                    ExpiresIn=3600
                )
                
                return {
                    "download_url": download_url,
                    "filename": f"meeting_{meeting_id}_summary.txt",
                    "storage": "cloud"
                }
            
            # Free/Starter - Local file
            else:
                if not Path(file_path).exists():
                    raise HTTPException(404, "Summary file not found on server")
                
                return FileResponse(
                    file_path,
                    media_type="application/json",
                    filename=f"meeting_{meeting_id}_summary.json"
                )
        
        else:
            raise HTTPException(400, f"Invalid download type: {type}")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Download error: {e}")
        raise HTTPException(500, f"Download failed: {str(e)}")
    
# ============================================================
# ADD THESE NEW ENDPOINTS TO YOUR meetings.py
# ============================================================

# Add this after the download endpoints (around line 900)

@router.post("/{meeting_id}/upload-to-cloud")
def upload_meeting_to_cloud(
    meeting_id: int,
    license_info: tuple = Depends(optional_license),
    db: Session = Depends(get_session)
):
    """
    ✅ NEW: Manual cloud upload for Pro/Business tiers.
    Uploads transcript and summary to B2, then deletes local copies.
    """
    license, tier_config = license_info
    tier = license.tier.lower() if license else "free"
    
    # Only Pro/Business can upload to cloud
    if tier not in ("professional", "business"):
        raise HTTPException(
            403,
            "Cloud storage is only available for Professional and Business tiers"
        )
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    
    # Verify ownership - check if meeting belongs to this license
    if meeting.license_id != license.id:
        raise HTTPException(403, "Not authorized")
    
    # Check if files are already in cloud
    if meeting.transcript_path and meeting.transcript_path.startswith("s3://"):
        return {
            "ok": True,
            "message": "Files already uploaded to cloud",
            "status": "already_uploaded"
        }
    
    try:
        from app.routers.storage_b2 import s3_client, get_bucket
        from pathlib import Path
        
        s3 = s3_client()
        bucket = get_bucket()
        tier_folder = tier
        
        uploaded_files = []
        
        # Upload transcript to B2
        if meeting.transcript_path and Path(meeting.transcript_path).exists():
            transcript_key = f"{tier_folder}/transcripts/transcript_{meeting_id}.txt"
            
            with open(meeting.transcript_path, 'rb') as f:
                s3.upload_fileobj(f, bucket, transcript_key)
            
            print(f"☁️ Uploaded transcript to B2: {transcript_key}")
            uploaded_files.append("transcript")
            
            # Update to B2 path and delete local
            old_path = meeting.transcript_path
            meeting.transcript_path = f"s3://{bucket}/{transcript_key}"
            Path(old_path).unlink()
            print(f"🗑️ Deleted local transcript: {old_path}")
        
        # Upload summary to B2
        if meeting.summary_path and Path(meeting.summary_path).exists():
            summary_key = f"{tier_folder}/summaries/summary_{meeting_id}.json"
            
            with open(meeting.summary_path, 'rb') as f:
                s3.upload_fileobj(f, bucket, summary_key)
            
            print(f"☁️ Uploaded summary to B2: {summary_key}")
            uploaded_files.append("summary")
            
            # Update to B2 path and delete local
            old_path = meeting.summary_path
            meeting.summary_path = f"s3://{bucket}/{summary_key}"
            Path(old_path).unlink()
            print(f"🗑️ Deleted local summary: {old_path}")
        
        # Update status
        meeting.status = "uploaded_to_cloud"
        meeting.step = "Files uploaded to cloud storage"
        db.add(meeting)
        db.commit()
        
        return {
            "ok": True,
            "message": f"Successfully uploaded {', '.join(uploaded_files)} to cloud",
            "uploaded_files": uploaded_files,
            "status": "uploaded"
        }
        
    except Exception as e:
        print(f"❌ Failed to upload to cloud: {e}")
        raise HTTPException(500, f"Failed to upload to cloud: {str(e)}")


@router.get("/{meeting_id}/cloud-status")
def get_cloud_status(
    meeting_id: int,
    license_info: tuple = Depends(optional_license),
    db: Session = Depends(get_session)
):
    """
    ✅ NEW: Check if meeting files are stored in cloud or locally.
    Returns storage location and whether upload is available.
    """
    license, tier_config = license_info
    tier = license.tier.lower() if license else "free"
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    
    # Check storage locations
    transcript_in_cloud = meeting.transcript_path and meeting.transcript_path.startswith("s3://")
    summary_in_cloud = meeting.summary_path and meeting.summary_path.startswith("s3://")
    
    # Determine overall storage status
    if transcript_in_cloud or summary_in_cloud:
        storage_location = "cloud"
    else:
        storage_location = "local"
    
    # Can upload to cloud if: Pro/Business tier + files are local + meeting is complete
    can_upload_to_cloud = (
        tier in ("professional", "business") and
        storage_location == "local" and
        meeting.status in ("completed", "delivered")
    )
    
    return {
        "storage_location": storage_location,
        "transcript_in_cloud": transcript_in_cloud,
        "summary_in_cloud": summary_in_cloud,
        "can_upload_to_cloud": can_upload_to_cloud,
        "tier": tier,
        "status": meeting.status
    }

# ADD THIS UTILITY FUNCTION to clean up audio files for Free/Starter after processing
def cleanup_media_file(meeting_id: int, db: Session):
    """
    Clean up audio/video media files after processing - ALL TIERS
    
    Called from pipeline after successful processing.
    Media files are ALWAYS deleted immediately for all tiers.
    
    Deletion Policy:
    - ALL TIERS: 
        * Media (audio/video): Deleted immediately ❌
    
    Retention Policy:
    - Free/Starter: 
        * Transcript/Summary: Kept temporarily for auto-download, then deleted on confirmation ⏰
        * Status changes to "ready_for_download" to trigger frontend auto-download
    - Pro/Business: 
        * Transcript/Summary: Stored permanently in B2 cloud ☁️
        * Status changes to "delivered"
    """
    meeting = db.get(Meeting, meeting_id)
    if not meeting or not meeting.audio_path:
        return
    
    try:
        if meeting.audio_path.startswith("s3://"):
            # Pro/Business - delete media from B2
            from app.routers.storage_b2 import s3_client, get_bucket
            s3 = s3_client()
            bucket = get_bucket()
            
            s3_path = meeting.audio_path.replace("s3://", "")
            parts = s3_path.split("/", 1)
            if len(parts) == 2:
                _, key = parts
                
                if "/temp/" in key:
                    s3.delete_object(Bucket=bucket, Key=key)
                    print(f"🗑️ Deleted media from B2: {key}")
                    
                    # Clear media path only, keep transcript/summary in B2
                    meeting.audio_path = None
                    meeting.status = "delivered"
                    meeting.step = "Complete. Transcript/summary stored in cloud."
                    db.add(meeting)
                    db.commit()
        else:
            # Free/Starter - delete local media file
            media_file = Path(meeting.audio_path)
            if media_file.exists():
                media_file.unlink()
                print(f"🗑️ Deleted local media: {media_file}")
                
                # Clear media path, set status to trigger auto-download
                meeting.audio_path = None
                meeting.status = "ready_for_download"
                meeting.step = "Processing complete. Ready to save to your device."
                db.add(meeting)
                db.commit()
                
                print(f"✅ Meeting {meeting_id} ready for auto-download to device")
    
    except Exception as e:
        print(f"⚠️ Failed to cleanup media: {e}")
        
def upload_transcript_summary_to_b2(meeting_id: int, db: Session):
    """
    Upload transcript and summary to B2 for Pro/Business tiers.
    Called after processing completes.
    """
    from app.routers.storage_b2 import s3_client, get_bucket
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        return
    
    # Only for Pro/Business with cloud storage
    if not meeting.license or meeting.license.tier.lower() not in ('professional', 'business'):
        print(f"⏭️ Skipping B2 upload for {meeting.license.tier if meeting.license else 'free'} tier")
        return
    
    s3 = s3_client()
    bucket = get_bucket()
    tier_folder = meeting.license.tier.lower()
    
    try:
        # Upload transcript to B2
        if meeting.transcript_path and Path(meeting.transcript_path).exists():
            transcript_key = f"{tier_folder}/transcripts/transcript_{meeting_id}.txt"
            
            with open(meeting.transcript_path, 'rb') as f:
                s3.upload_fileobj(f, bucket, transcript_key)
            
            print(f"☁️ Uploaded transcript to B2: {transcript_key}")
            
            # Update to B2 path
            old_path = meeting.transcript_path
            meeting.transcript_path = f"s3://{bucket}/{transcript_key}"
            
            # Delete local file
            Path(old_path).unlink()
            print(f"🗑️ Deleted local transcript: {old_path}")
        
        # Upload summary to B2
        if meeting.summary_path and Path(meeting.summary_path).exists():
            summary_key = f"{tier_folder}/summaries/summary_{meeting_id}.json"
            
            with open(meeting.summary_path, 'rb') as f:
                s3.upload_fileobj(f, bucket, summary_key)
            
            print(f"☁️ Uploaded summary to B2: {summary_key}")
            
            # Update to B2 path
            old_path = meeting.summary_path
            meeting.summary_path = f"s3://{bucket}/{summary_key}"
            
            # Delete local file
            Path(old_path).unlink()
            print(f"🗑️ Deleted local summary: {old_path}")
        
        meeting.status = "delivered"
        meeting.step = "Complete. Files stored in cloud."
        db.add(meeting)
        db.commit()
        
        print(f"✅ Meeting {meeting_id} files uploaded to B2 and local copies deleted")
        
    except Exception as e:
        print(f"❌ Failed to upload to B2: {e}")
        raise       

# MODIFY your existing delete endpoint to handle B2 files
@router.delete("/{meeting_id}")
def delete_meeting(
    meeting_id: int,
    license_info: tuple = Depends(optional_license),
    db: Session = Depends(get_session)
):
    """Delete a meeting and its associated files (local and B2)"""
    license, tier_config = license_info
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Not found")
    
    # Verify ownership - check if meeting belongs to this license
    if license:
        # User has a license - verify they own this meeting
        if meeting.license_id != license.id:
            raise HTTPException(
                status_code=403, 
                detail="Cannot delete meeting belonging to another user"
            )
    else:
        # No license provided - only allow if meeting has no license (legacy/free)
        if meeting.license_id is not None:
            raise HTTPException(
                status_code=403,
                detail="License required to delete this meeting"
            )
    
    # Delete B2 files if Professional/Business tier
    if meeting.audio_path and meeting.audio_path.startswith("s3://"):
        try:
            from app.routers.storage_b2 import s3_client, get_bucket
            s3 = s3_client()
            bucket = get_bucket()
            
            # Extract key from s3://bucket/key format
            s3_path = meeting.audio_path.replace("s3://", "")
            parts = s3_path.split("/", 1)
            if len(parts) == 2:
                _, key = parts
                s3.delete_object(Bucket=bucket, Key=key)
                print(f"🗑️ Deleted B2 file: {key}")
        except Exception as e:
            print(f"⚠️ Failed to delete B2 file: {e}")
    
    # Delete local files
    if meeting.audio_path and not meeting.audio_path.startswith("s3://"):
        if Path(meeting.audio_path).exists():
            Path(meeting.audio_path).unlink()
    
    if meeting.transcript_path and Path(meeting.transcript_path).exists():
        Path(meeting.transcript_path).unlink()
    
    if meeting.summary_path and Path(meeting.summary_path).exists():
        Path(meeting.summary_path).unlink()
    
    # Delete meeting record
    db.delete(meeting)
    db.commit()
    
    return {"success": True, "message": "Meeting deleted"}

@router.post("/{meeting_id}/confirm-download")
def confirm_download(
    meeting_id: int,
    license_info: tuple = Depends(optional_license),
    db: Session = Depends(get_session)
):
    """
    FREE/STARTER ONLY: Confirm files have been downloaded to device.
    After confirmation, server deletes all local copies.
    
    This endpoint ensures "nothing is stored locally" for Free/Starter tiers.
    """
    license, tier_config = license_info
    tier = license.tier.lower() if license else "free"
    
    # Only Free/Starter should use this
    if tier not in ("free", "starter"):
        raise HTTPException(
            400,
            "This endpoint is for Free/Starter tiers only. "
            "Pro/Business tiers use cloud storage."
        )
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    
    # Verify ownership - check if meeting belongs to this license
    if license:
        if meeting.license_id != license.id:
            raise HTTPException(403, "Not authorized")
    else:
        # No license but meeting has one - not authorized
        if meeting.license_id is not None:
            raise HTTPException(403, "Not authorized")
    
    try:
        # Delete transcript from server
        if meeting.transcript_path and Path(meeting.transcript_path).exists():
            Path(meeting.transcript_path).unlink()
            print(f"🗑️ Deleted transcript from server: {meeting.transcript_path}")
        
        # Delete summary from server
        if meeting.summary_path and Path(meeting.summary_path).exists():
            Path(meeting.summary_path).unlink()
            print(f"🗑️ Deleted summary from server: {meeting.summary_path}")
        
        # Update meeting status
        meeting.status = "downloaded_to_device"
        meeting.step = "Files saved to your device. Server copies deleted."
        meeting.transcript_path = None
        meeting.summary_path = None
        
        db.add(meeting)
        db.commit()
        
        return {
            "ok": True,
            "message": "Files deleted from server successfully",
            "storage_location": "device",
            "note": "Your files are now only on your device"
        }
    
    except Exception as e:
        print(f"⚠️ Failed to delete files from server: {e}")
        raise HTTPException(500, f"Failed to delete server files: {str(e)}")