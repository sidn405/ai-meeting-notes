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

def get_license_from_key(
    x_license_key: str = Header(..., alias="X-License-Key"),
    db: Session = Depends(get_session)
) -> License:
    """
    Get license from key - ALL users must have a license.
    Uses direct database lookup (no complex validation).
    Raises 401 if key missing or doesn't match any license.
    """
    if not x_license_key:
        raise HTTPException(
            status_code=401,
            detail="License key required. All users must have a license."
        )
    
    # Direct database lookup
    license = db.exec(
        select(License).where(License.license_key == x_license_key)
    ).first()
    
    if not license:
        raise HTTPException(
            status_code=401,
            detail="Invalid license key. Please check your license."
        )
    
    return license

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
    license: License = Depends(get_license_from_key),
    db = Depends(get_session),
):
    """
    Upload - ALL TIERS can upload audio/video files
    
    Important distinction:
    - File upload (audio/video): ALL tiers ✅
    - Live video recording: Business tier only (UI feature) 🎥
    
    Storage architecture:
    - All tiers: Files initially saved to device after processing
    - Free/Starter: Device storage only (auto-delete from server after download)
    - Pro/Business: Device storage initially, with optional cloud upload for permanent storage
    """
    tier = license.tier.lower()
    tier_config = TIER_LIMITS[license.tier]
    
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
        license_id=license.id  # License always exists now
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    mid = m.id

    # Track usage (all users have licenses now)
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
        retention_note = "Will be saved to your device after processing. Server deletes files after download confirmation."
        response_data["auto_download_required"] = True
        response_data["storage_location"] = "device"
        response_data["cloud_upload_available"] = False
    else:  # Pro/Business
        retention_note = "Will be saved to your device after processing. You can optionally upload to cloud for permanent storage."
        response_data["auto_download_required"] = True  # All tiers download to device first
        response_data["storage_location"] = "device"  # Initially on device
        response_data["cloud_upload_available"] = True

    response_data["retention"] = retention_note
    return response_data
    
@router.get("/stats")
def get_meeting_stats(
    license: License = Depends(get_license_from_key),
    db: Session = Depends(get_session),
):
    """
    Get meeting statistics for the current user
    Returns counts of total, completed, processing, and current month meetings
    """
    
    from datetime import datetime
    from sqlmodel import func
    
    # Filter all queries by license_id
    total_meetings = db.exec(
        select(func.count(Meeting.id)).where(Meeting.license_id == license.id)
    ).one()
    
    completed_meetings = db.exec(
        select(func.count(Meeting.id)).where(
            (Meeting.license_id == license.id) & (Meeting.status == "delivered")
        )
    ).one()
    
    processing_meetings = db.exec(
        select(func.count(Meeting.id)).where(
            (Meeting.license_id == license.id) & 
            ((Meeting.status == "processing") | (Meeting.status == "queued"))
        )
    ).one()
    
    # Meetings this month
    now = datetime.now()
    first_day_of_month = datetime(now.year, now.month, 1)
    
    meetings_this_month = db.exec(
        select(func.count(Meeting.id)).where(
            (Meeting.license_id == license.id) & 
            (Meeting.created_at >= first_day_of_month)
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
def list_meetings(
    license: License = Depends(get_license_from_key),  # ADD THIS
    db: Session = Depends(get_session)
):
    """Get all meetings for current user ordered by creation date (newest first) with storage info"""
    try:
        # Filter by license_id
        meetings = db.exec(
            select(Meeting)
            .where(Meeting.license_id == license.id)  # ADD THIS
            .order_by(Meeting.created_at.desc())
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
def meeting_status(
    meeting_id: int,
    license: License = Depends(get_license_from_key),  # ADD THIS
    db: Session = Depends(get_session)
):
    """Get meeting status with cloud storage info"""
    # Get meeting and verify ownership
    m = db.get(Meeting, meeting_id)
    if not m:
        raise HTTPException(404, "Not found")
    
    # Security check: verify this meeting belongs to this user
    if m.license_id != license.id:
        raise HTTPException(403, "Access denied - this meeting belongs to another user")
    
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
    license: License = Depends(get_license_from_key),
    db = Depends(get_session),
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
            status="queued",
            license_id=license.id  # Set license_id
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Track usage (all users have licenses now)
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
    license: License = Depends(get_license_from_key),
    db = Depends(get_session),
):
    """Alias for from-text (already synchronous)"""
    return await create_from_text(title, transcript, email_to, license, db)

@router.post("/transcribe-only")
async def transcribe_only(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: str | None = Form(None),
    license: License = Depends(get_license_from_key),
    db = Depends(get_session),
):
    """Save transcript without summarization"""
    
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
            step="Transcript saved",
            license_id=license.id  # Set license_id
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Track usage (all users have licenses now)
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
    license: License = Depends(get_license_from_key),
    db = Depends(get_session),
):
    """Upload and transcribe ONLY (no summarization)"""
    tier_config = TIER_LIMITS[license.tier]
    
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
            status="queued",
            license_id=license.id  # Set license_id
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Track usage (all users have licenses now)
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
    license: License = Depends(get_license_from_key),
    db = Depends(get_session),
):
    """Upload and transcribe (with summarization)"""
    tier_config = TIER_LIMITS[license.tier]
    
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
            status="queued",
            license_id=license.id  # Set license_id
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Track usage (all users have licenses now)
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
    license: License = Depends(get_license_from_key),
    db = Depends(get_session),
):
    """Create meeting from S3 URL (for multipart uploads)"""
    tier_config = TIER_LIMITS[license.tier]
    
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
            status="queued",
            license_id=license.id  # Set license_id
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id
    
    # Track usage (all users have licenses now)
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
    license: License = Depends(get_license_from_key),
    db = Depends(get_session),
):
    """Create meeting from S3 URL - transcribe only"""
    tier_config = TIER_LIMITS[license.tier]
    
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
            status="queued",
            license_id=license.id  # Set license_id
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id
    
    # Track usage (all users have licenses now)
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
def get_meeting(
    meeting_id: int,
    license: License = Depends(get_license_from_key)
):
    """Get meeting details"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(status_code=404, detail="Not found")
        
        # Security check
        if m.license_id != license.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return m


@router.get("/{meeting_id}/download/transcript")
def download_transcript(
    meeting_id: int,
    license: License = Depends(get_license_from_key)
):
    """Download meeting transcript"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(status_code=404, detail="Not found")
        
        # Security check
        if m.license_id != license.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not (m.transcript_path and Path(m.transcript_path).exists()):
            raise HTTPException(status_code=404, detail="Transcript not found")
        
        return FileResponse(
            m.transcript_path,
            media_type="text/plain",
            filename=Path(m.transcript_path).name
        )


@router.get("/{meeting_id}/download/summary")
def download_summary(
    meeting_id: int,
    license: License = Depends(get_license_from_key)
):
    """Download meeting summary (as file attachment)"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(status_code=404, detail="Not found")
        
        # Security check
        if m.license_id != license.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not (m.summary_path and Path(m.summary_path).exists()):
            raise HTTPException(status_code=404, detail="Summary not found")
        
        return FileResponse(
            m.summary_path,
            media_type="application/json",
            filename=Path(m.summary_path).name
        )


@router.get("/{meeting_id}/summary")
def get_summary(
    meeting_id: int,
    license: License = Depends(get_license_from_key)
):
    """Get meeting summary as JSON (for reading, not downloading)"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(status_code=404, detail="Not found")
        
        # Security check
        if m.license_id != license.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not (m.summary_path and Path(m.summary_path).exists()):
            raise HTTPException(status_code=404, detail="Summary not found")
        
        summary_text = Path(m.summary_path).read_text(encoding="utf-8")
        return json.loads(summary_text)


@router.get("/{meeting_id}/transcript")
def get_transcript(
    meeting_id: int,
    license: License = Depends(get_license_from_key)
):
    """Get meeting transcript as JSON (for reading, not downloading)"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Security check
        if m.license_id != license.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
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
    
    # Send email directly (not queued)
    try:
        # Load summary JSON if available
        summary_json = None
        if has_summary and meeting.summary_path:
            with open(meeting.summary_path, 'r') as f:
                summary_json = json.load(f)
        
        # Get the appropriate file path
        file_path = meeting.summary_path if has_summary else meeting.transcript_path
        
        # send_summary_email expects: meeting_id, summary_json, summary_path, email_to
        send_summary_email(meeting_id, summary_json, file_path, email)
        
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
    x_license_key: str = Header(..., alias="X-License-Key"),  # Required now
    db: Session = Depends(get_session)
):
    """Download meeting files - from B2 for Pro/Business, from server for Free/Starter"""
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    
    # Verify ownership - all meetings have licenses now
    if not meeting.license_id:
        raise HTTPException(500, "Meeting has no license - data integrity issue")
    
    # Look up the meeting's license and compare keys
    meeting_license = db.get(License, meeting.license_id)
    if not meeting_license or meeting_license.license_key != x_license_key:
        raise HTTPException(403, "Not authorized - license key does not match")
    
    # Set tier from the meeting's license
    tier = meeting_license.tier.lower()
    
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
    x_license_key: str = Header(..., alias="X-License-Key"),
    db: Session = Depends(get_session)
):
    """
    ✅ NEW: Manual cloud upload for Pro/Business tiers.
    Uploads transcript and summary to B2, then deletes local copies.
    """
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    
    # Verify ownership - all meetings have licenses
    if not meeting.license_id:
        raise HTTPException(500, "Meeting has no license - data integrity issue")
    
    meeting_license = db.get(License, meeting.license_id)
    if not meeting_license or meeting_license.license_key != x_license_key:
        raise HTTPException(403, "Not authorized - license key does not match")
    
    tier = meeting_license.tier.lower()
    
    # Only Pro/Business can upload to cloud
    if tier not in ("professional", "business"):
        raise HTTPException(
            403,
            "Cloud storage is only available for Professional and Business tiers"
        )
    
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
    license: License = Depends(get_license_from_key),
    db: Session = Depends(get_session)
):
    """
    ✅ NEW: Check if meeting files are stored in cloud or locally.
    Returns storage location and whether upload is available.
    """
    tier = license.tier.lower()
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    
    # Verify ownership
    if meeting.license_id != license.id:
        raise HTTPException(403, "Not authorized")
    
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
    x_license_key: str = Header(..., alias="X-License-Key"),
    db: Session = Depends(get_session)
):
    """Delete a meeting and its associated files (local and B2)"""
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Not found")
    
    # Verify ownership - all meetings have licenses
    if not meeting.license_id:
        raise HTTPException(500, "Meeting has no license - data integrity issue")
        
    meeting_license = db.get(License, meeting.license_id)
    if not meeting_license or meeting_license.license_key != x_license_key:
        raise HTTPException(403, "Cannot delete meeting belonging to another user")
    
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
    x_license_key: str = Header(..., alias="X-License-Key"),
    db: Session = Depends(get_session)
):
    """
    ALL TIERS: Confirm files have been downloaded to device.
    After confirmation, server deletes all local copies.
    
    - All tiers download files to device initially
    - Free/Starter: Files stay on device only
    - Pro/Business: Files on device, with optional cloud upload
    
    This endpoint is for confirming local server files can be deleted.
    Cannot be used for files already in cloud storage.
    """
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    
    # Verify ownership - all meetings have licenses
    if not meeting.license_id:
        raise HTTPException(500, "Meeting has no license - data integrity issue")
        
    meeting_license = db.get(License, meeting.license_id)
    if not meeting_license or meeting_license.license_key != x_license_key:
        raise HTTPException(403, "Not authorized")
    
    # Check if files are in cloud - if so, can't confirm local download
    transcript_in_cloud = meeting.transcript_path and meeting.transcript_path.startswith("s3://")
    summary_in_cloud = meeting.summary_path and meeting.summary_path.startswith("s3://")
    
    if transcript_in_cloud or summary_in_cloud:
        raise HTTPException(
            400,
            "Cannot confirm download for cloud-stored files. "
            "Files are already permanently stored in cloud."
        )
    
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

# ============================================================
# OFFLINE ACCESS - Available to ALL users
# ============================================================

@router.get("/{meeting_id}/download-all")
def download_meeting_package(
    meeting_id: int,
    format: str = Query("zip", description="zip or html"),
    x_license_key: str = Header(..., alias="X-License-Key"),
    db: Session = Depends(get_session)
):
    """
    Download complete meeting package for offline access.
    Available to ALL users.
    
    Formats:
    - zip: All files in a ZIP archive (transcript, summary, metadata)
    - html: Self-contained HTML viewer with all data embedded
    """
    import zipfile
    import tempfile
    from datetime import datetime
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    
    # Verify ownership
    if not meeting.license_id:
        raise HTTPException(500, "Meeting has no license")
    
    meeting_license = db.get(License, meeting.license_id)
    if not meeting_license or meeting_license.license_key != x_license_key:
        raise HTTPException(403, "Not authorized")
    
    # Check if files are in cloud storage
    files_in_cloud = (
        (meeting.transcript_path and meeting.transcript_path.startswith("s3://")) or
        (meeting.summary_path and meeting.summary_path.startswith("s3://"))
    )
    
    if files_in_cloud:
        raise HTTPException(
            400,
            "Cannot create offline package for cloud-stored files. "
            "Please download files individually from cloud storage."
        )
    
    # Verify files exist locally
    has_transcript = meeting.transcript_path and Path(meeting.transcript_path).exists()
    has_summary = meeting.summary_path and Path(meeting.summary_path).exists()
    
    if not has_transcript and not has_summary:
        raise HTTPException(404, "No meeting files available for download")
    
    if format == "html":
        # Generate self-contained HTML viewer
        html_content = generate_offline_html_viewer(meeting, db)
        
        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.html')
        temp_file.write(html_content)
        temp_file.close()
        
        return FileResponse(
            temp_file.name,
            media_type="text/html",
            filename=f"meeting_{meeting_id}_{meeting.title.replace(' ', '_')}.html",
            background=BackgroundTasks()
        )
    
    elif format == "zip":
        # Create ZIP package with all files
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_zip.close()
        
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add transcript
            if has_transcript:
                zipf.write(
                    meeting.transcript_path,
                    f"transcript.txt"
                )
            
            # Add summary
            if has_summary:
                zipf.write(
                    meeting.summary_path,
                    f"summary.json"
                )
            
            # Add metadata file
            metadata = {
                "meeting_id": meeting.id,
                "title": meeting.title,
                "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
                "status": meeting.status,
                "media_type": meeting.media_type,
                "has_transcript": has_transcript,
                "has_summary": has_summary,
                "download_date": datetime.now().isoformat()
            }
            
            zipf.writestr("metadata.json", json.dumps(metadata, indent=2))
            
            # Add README
            readme = f"""# Meeting: {meeting.title}

Downloaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Contents

- transcript.txt: Full meeting transcript
- summary.json: AI-generated meeting summary
- metadata.json: Meeting information

## Offline Access

All files in this archive work offline and do not require an internet connection.

You can view the summary.json in any text editor or JSON viewer.
"""
            zipf.writestr("README.md", readme)
        
        return FileResponse(
            temp_zip.name,
            media_type="application/zip",
            filename=f"meeting_{meeting_id}_{meeting.title.replace(' ', '_')}.zip"
        )
    
    else:
        raise HTTPException(400, f"Invalid format: {format}. Use 'zip' or 'html'")


def generate_offline_html_viewer(meeting: Meeting, db: Session) -> str:
    """
    Generate a self-contained HTML file with all meeting data embedded.
    Works completely offline with no external dependencies.
    """
    from datetime import datetime
    
    # Load transcript
    transcript_text = ""
    if meeting.transcript_path and Path(meeting.transcript_path).exists():
        with open(meeting.transcript_path, 'r') as f:
            transcript_text = f.read()
    
    # Load summary
    summary_data = {}
    if meeting.summary_path and Path(meeting.summary_path).exists():
        with open(meeting.summary_path, 'r') as f:
            summary_data = json.load(f)
    
    # Extract summary sections
    summary_text = summary_data.get('summary', 'No summary available')
    action_items = summary_data.get('action_items', [])
    key_points = summary_data.get('key_points', [])
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{meeting.title} - Meeting Summary</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
        }}
        
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
        }}
        
        .header .meta {{
            opacity: 0.9;
            font-size: 14px;
        }}
        
        .offline-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 12px;
            margin-top: 10px;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        .section {{
            margin-bottom: 30px;
        }}
        
        .section h2 {{
            font-size: 20px;
            color: #667eea;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }}
        
        .tabs {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }}
        
        .tab {{
            padding: 10px 20px;
            cursor: pointer;
            background: transparent;
            border: none;
            font-size: 16px;
            color: #666;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
        }}
        
        .tab:hover {{
            color: #667eea;
        }}
        
        .tab.active {{
            color: #667eea;
            border-bottom-color: #667eea;
        }}
        
        .tab-content {{
            display: none;
        }}
        
        .tab-content.active {{
            display: block;
        }}
        
        .summary-text {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 8px;
            line-height: 1.8;
        }}
        
        .list-item {{
            background: #f9f9f9;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 6px;
            border-left: 4px solid #667eea;
        }}
        
        .transcript {{
            background: #fafafa;
            padding: 20px;
            border-radius: 8px;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.8;
            max-height: 600px;
            overflow-y: auto;
        }}
        
        .no-content {{
            color: #999;
            font-style: italic;
            padding: 20px;
            text-align: center;
        }}
        
        .footer {{
            background: #f9f9f9;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
        
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
            }}
            .tabs {{
                display: none;
            }}
            .tab-content {{
                display: block !important;
                page-break-before: always;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{meeting.title}</h1>
            <div class="meta">
                Meeting ID: {meeting.id} | 
                Created: {meeting.created_at.strftime('%Y-%m-%d %H:%M') if meeting.created_at else 'N/A'} |
                Status: {meeting.status}
            </div>
            <div class="offline-badge">✓ Works Offline</div>
        </div>
        
        <div class="content">
            <div class="tabs">
                <button class="tab active" onclick="showTab('summary')">Summary</button>
                <button class="tab" onclick="showTab('action-items')">Action Items</button>
                <button class="tab" onclick="showTab('key-points')">Key Points</button>
                <button class="tab" onclick="showTab('transcript')">Full Transcript</button>
            </div>
            
            <div id="summary" class="tab-content active">
                <div class="section">
                    <h2>Meeting Summary</h2>
                    <div class="summary-text">{summary_text if summary_text else '<div class="no-content">No summary available</div>'}</div>
                </div>
            </div>
            
            <div id="action-items" class="tab-content">
                <div class="section">
                    <h2>Action Items</h2>
                    {''.join([f'<div class="list-item">{item}</div>' for item in action_items]) if action_items else '<div class="no-content">No action items</div>'}
                </div>
            </div>
            
            <div id="key-points" class="tab-content">
                <div class="section">
                    <h2>Key Points</h2>
                    {''.join([f'<div class="list-item">{point}</div>' for point in key_points]) if key_points else '<div class="no-content">No key points</div>'}
                </div>
            </div>
            
            <div id="transcript" class="tab-content">
                <div class="section">
                    <h2>Full Transcript</h2>
                    <div class="transcript">{transcript_text if transcript_text else '<div class="no-content">No transcript available</div>'}</div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
            This file works completely offline and contains all meeting data.
        </div>
    </div>
    
    <script>
        function showTab(tabName) {{
            // Hide all tab contents
            const contents = document.querySelectorAll('.tab-content');
            contents.forEach(content => content.classList.remove('active'));
            
            // Remove active class from all tabs
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => tab.classList.remove('active'));
            
            // Show selected tab content
            document.getElementById(tabName).classList.add('active');
            
            // Add active class to clicked tab
            event.target.classList.add('active');
        }}
    </script>
</body>
</html>"""
    
    return html