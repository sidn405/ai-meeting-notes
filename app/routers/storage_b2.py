# routers/storage_b2.py - ULTIMATE FINAL VERSION

import os, time, mimetypes
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

import boto3
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from sqlmodel import Session, select

from app.models import Meeting, License, LicenseTier, TIER_LIMITS
from app.services.pipeline import process_meeting
from app.routers.meetings import require_license, track_meeting_usage
from app.db import get_session
from fastapi import UploadFile, Form, File

router = APIRouter(prefix="/storage", tags=["storage"])

# ---------- B2 S3 client ----------
def s3_client():
    """Create B2-compatible S3 client"""
    from botocore.config import Config
    
    endpoint = os.getenv("S3_ENDPOINT")
    region = os.getenv("S3_REGION", "us-west-004")
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    if not all([endpoint, access_key, secret_key]):
        raise HTTPException(500, "B2 credentials not configured")
    
    config = Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path'}
    )
    
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=config
    )

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

def get_bucket() -> str:
    """Get S3 bucket name from environment"""
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise HTTPException(500, "S3_BUCKET not set in environment")
    return bucket

# ---------- Models ----------
class PresignUploadIn(BaseModel):
    filename: str = Field(..., examples=["meeting.m4a", "meeting.mp4"])
    content_type: Optional[str] = Field(None, examples=["audio/m4a", "video/mp4"])
    file_type: str = Field(..., examples=["audio", "video"])

class PresignUploadOut(BaseModel):
    upload_url: str
    key: str
    expires_in: int

class ConfirmUploadIn(BaseModel):
    key: str
    size_bytes: int
    title: Optional[str] = None
    language: Optional[str] = None
    hints: Optional[str] = None
    email_to: Optional[str] = None
    file_type: str = Field(..., examples=["audio", "video"])

# ---------- Helpers ----------
def _key_for(license_key: str, tier: str, filename: str, file_type: str = "audio") -> str:
    """
    Create a unique key for Backblaze uploads.
    All files go to temp/ folder since everything gets deleted after processing.
    """
    name = Path(filename).name
    ts = int(time.time())
    return f"{tier}/{license_key}/temp/{file_type}-{ts}-{name}"

def _content_key_for(license_key: str, tier: str, content_type: str, meeting_id: int) -> str:
    """
    Create key for permanent content (transcripts, summaries).
    Only used for Professional/Business tiers.
    """
    ts = int(time.time())
    ext = "txt" if content_type == "transcript" else "json"
    return f"{tier}/{license_key}/content/{content_type}-{meeting_id}-{ts}.{ext}"

# ---------- Routes ----------

@router.post("/presign-upload", response_model=PresignUploadOut)
def presign_upload(
    body: PresignUploadIn,
    license_info: tuple = Depends(require_license),
    db: Session = Depends(get_session)
):
    """
    PROFESSIONAL/BUSINESS ONLY: Get presigned URL for direct B2 upload
    
    Supports both audio and video files for all these tiers.
    Note: Live video recording is a Business-only UI feature, but file uploads
    support video for both Pro and Business.
    
    Workflow:
    1. Client calls this to get upload URL
    2. Client uploads file directly to B2
    3. Client calls /confirm-upload
    4. Media deleted after processing, transcript/summary stored in B2
    """
    license, tier_config = license_info
    tier = license.tier.lower()

    # Only Professional/Business can use cloud storage
    if tier not in ("professional", "business"):
        raise HTTPException(
            403, 
            "Cloud uploads require Professional or Business plan. "
            "Free and Starter tiers process locally."
        )

    # Check quota
    track_meeting_usage(db, license.license_key)

    # Generate upload key
    filename = body.filename or f"{body.file_type}"
    ctype = body.content_type or (mimetypes.guess_type(filename)[0] or "application/octet-stream")
    key = _key_for(license.license_key, tier, filename, body.file_type)

    # Generate presigned URL (30 min for large files)
    s3 = s3_client()
    bucket = get_bucket()
    expires_in = 30 * 60

    upload_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": bucket, 
            "Key": key, 
            "ContentType": ctype
        },
        ExpiresIn=expires_in,
    )
    
    return PresignUploadOut(
        upload_url=upload_url, 
        key=key, 
        expires_in=expires_in
    )


@router.post("/confirm-upload")
def confirm_upload(
    body: ConfirmUploadIn,
    background: BackgroundTasks,
    license_info: tuple = Depends(require_license),
    db: Session = Depends(get_session)
):
    """
    PROFESSIONAL/BUSINESS ONLY: Confirm upload and start processing
    
    Accepts both audio and video files.
    Media deleted after processing, transcript/summary stored permanently in B2.
    """
    license, tier_config = license_info
    tier = license.tier.lower()

    if tier not in ("professional", "business"):
        raise HTTPException(403, "Cloud uploads require Professional or Business plan")

    # Enforce size limit
    size_mb = body.size_bytes / (1024 * 1024)
    max_mb = tier_config.get("max_file_size_mb") or TIER_LIMITS[tier]["max_file_size_mb"]
    if size_mb > max_mb:
        raise HTTPException(413, f"File exceeds plan limit of {max_mb} MB")

    track_meeting_usage(db, license.license_key)

    # Create meeting record
    bucket = get_bucket()
    audio_uri = f"s3://{bucket}/{body.key}"
    
    meeting = Meeting(
        title=body.title or Path(body.key).name,
        audio_path=audio_uri,
        email_to=body.email_to or license.email,
        status="queued",
        progress=0,
        step="queued",
        media_type=body.file_type
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Trigger processing
    try:
        background.add_task(
            process_meeting,
            meeting_id=meeting.id,
            language=body.language,
            hints=body.hints,
        )
    except TypeError:
        background.add_task(process_meeting, meeting.id)

    return {
        "ok": True, 
        "meeting_id": meeting.id, 
        "audio_uri": audio_uri,
        "tier": tier,
        "cloud_storage": True,
        "file_type": body.file_type,
        "note": f"{body.file_type.title()} will be deleted after processing. Transcript/summary retained in cloud."
    }


@router.get("/presign-download")
def presign_download(
    key: str,
    license_info: tuple = Depends(require_license),
    db: Session = Depends(get_session)
):
    """
    PROFESSIONAL/BUSINESS ONLY: Get presigned download URL for B2 content
    
    Used for downloading transcripts and summaries from B2.
    Media files not available (deleted after processing).
    """
    license, tier_config = license_info
    tier = license.tier.lower()
    
    if tier not in ("professional", "business"):
        raise HTTPException(
            403,
            "Cloud downloads require Professional or Business plan."
        )
    
    bucket = get_bucket()
    s3_uri = f"s3://{bucket}/{key}"

    # Verify ownership
    owned = db.exec(
        select(Meeting).where(
            (Meeting.transcript_path == s3_uri) | (Meeting.summary_path == s3_uri)
        ).where(
            Meeting.email_to == license.email
        )
    ).first()
    
    if not owned:
        raise HTTPException(403, "Not allowed to access this file")

    # Don't allow downloads from temp/ folder
    if "/temp/" in key:
        raise HTTPException(
            404,
            "Media files are not available. Only transcripts and summaries are retained."
        )

    # Generate presigned download URL
    s3 = s3_client()
    expires_in = 15 * 60
    
    try:
        url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        
        return {"url": url, "expires_in": expires_in}
    except Exception as e:
        raise HTTPException(500, f"Failed to generate download URL: {str(e)}")


# Helper for pipeline to upload content to B2
def upload_content_to_b2(
    license_key: str,
    tier: str,
    meeting_id: int,
    content: str,
    content_type: str
) -> str:
    """
    Upload transcript or summary to B2 (Pro/Business only).
    Returns the S3 key.
    """
    s3 = s3_client()
    bucket = get_bucket()
    
    key = _content_key_for(license_key, tier, content_type, meeting_id)
    content_type_header = "text/plain" if content_type == "transcript" else "application/json"
    
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=content.encode('utf-8'),
        ContentType=content_type_header
    )
    
    print(f"☁️ Uploaded {content_type} to B2: {key}")
    return key


# Cleanup function - scheduled job
def cleanup_orphaned_server_files():
    """
    Clean up orphaned Free/Starter files that failed auto-download.
    Run as daily cron job to catch edge cases.
    
    Only deletes files older than 24 hours with status "ready_for_download"
    (meaning auto-download never completed)
    """
    from app.db import DATA_DIR
    cutoff = datetime.now() - timedelta(hours=24)
    
    with get_session() as db:
        # Find meetings stuck in ready_for_download status
        orphaned = db.exec(
            select(Meeting).where(
                Meeting.created_at < cutoff,
                Meeting.status == "ready_for_download"
            )
        ).all()
        
        for meeting in orphaned:
            # Only cleanup Free/Starter (no S3 paths)
            if meeting.audio_path and not meeting.audio_path.startswith("s3://"):
                try:
                    # Delete transcript
                    if meeting.transcript_path and Path(meeting.transcript_path).exists():
                        Path(meeting.transcript_path).unlink()
                        meeting.transcript_path = None
                    
                    # Delete summary
                    if meeting.summary_path and Path(meeting.summary_path).exists():
                        Path(meeting.summary_path).unlink()
                        meeting.summary_path = None
                    
                    meeting.status = "auto_download_failed"
                    meeting.step = "Auto-download failed after 24 hours. Files removed from server."
                    
                    db.add(meeting)
                    db.commit()
                    
                    print(f"🗑️ Cleaned up orphaned meeting {meeting.id}")
                except Exception as e:
                    print(f"⚠️ Failed to cleanup orphaned meeting {meeting.id}: {e}")
