# routers/storage_b2.py
import os, time, mimetypes
from pathlib import Path
from typing import Optional

import boto3
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from app.utils.storage import s3_client, get_presigned_url, S3_BUCKET
from dotenv import load_dotenv
# ---- import your existing pieces ----
from app.models import LicenseTier, Meeting, TIER_LIMITS                    # your SQLModel Meeting + tiers
from app.services.pipeline import process_meeting                       # your existing pipeline runner
#from auth import get_current_user                          # your existing auth (return user dict or model)
from app.routers.meetings import require_license, track_meeting_usage          # (helper you may already have; see fallback below)
from sqlmodel import Session, select
from app.db import get_session                              # your DB session dependency
from fastapi import UploadFile, Form, File
# Models
from ..models import Meeting, License, LicenseTier, TIER_LIMITS


router = APIRouter(prefix="/storage", tags=["storage"])

# ---------- B2 S3 client ----------
def s3_client():
    from botocore.config import Config
    
    endpoint = os.getenv("S3_ENDPOINT")
    region = os.getenv("S3_REGION", "us-west-004")
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # B2-specific configuration
    config = Config(
        signature_version='s3v4',
        s3={
            'addressing_style': 'path'  # B2 requires path-style addressing
        }
    )
    
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=config
    )

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")  # robust load

def get_bucket() -> str:
    b = os.getenv("S3_BUCKET")
    if not b:
        # Using HTTPException gives you a clear error in the API
        from fastapi import HTTPException
        raise HTTPException(500, "S3_BUCKET not set in environment")
    return b

# ---------- Models ----------
class PresignUploadIn(BaseModel):
    filename: str = Field(..., examples=["meeting.m4a"])
    content_type: Optional[str] = Field(None, examples=["audio/m4a"])

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
    slack_channel: Optional[str] = None
    compute_type: Optional[str] = None

class PresignDownloadOut(BaseModel):
    url: str
    expires_in: int

# ---------- Helpers ----------
def _key_for(license_key: str, tier: str, filename: str) -> str:
    """Create a clean unique key for Backblaze uploads."""
    name = Path(filename).name
    ts = int(time.time())
    return f"{tier}/{license_key}/{ts}-{name}"

# ---------- Routes ----------

@router.post("/upload-direct")
async def upload_direct(
    background: BackgroundTasks,
    license_info: tuple = Depends(require_license),
    db: Session = Depends(get_session),
    file: UploadFile = File(...),
    title: str = Form(...),
    language: str = Form("en"),
    hints: str = Form(None)
):
    """Mobile app upload - handles all tiers"""
    license, tier_config = license_info
    tier = license.tier.lower()

    # Read file
    file_content = await file.read()
    file_size = len(file_content)
    
    # Check size limit (all tiers)
    size_mb = file_size / (1024 * 1024)
    max_mb = TIER_LIMITS[tier]["max_file_size_mb"]
    if size_mb > max_mb:
        raise HTTPException(413, f"File exceeds plan limit of {max_mb} MB")

    # Track usage (all tiers)
    track_meeting_usage(db, license.license_key)

    # Generate key
    key = _key_for(license.license_key, tier, file.filename)
    
    # ONLY Professional/Business upload to B2
    audio_uri = None
    if tier in ("professional", "business"):
        s3 = s3_client()
        s3.put_object(
            Bucket=get_bucket(),
            Key=key,
            Body=file_content,
            ContentType=file.content_type or "application/octet-stream"
        )
        bucket = get_bucket()
        audio_uri = f"s3://{bucket}/{key}"
    else:
        # Starter: Save temporarily for processing, will be deleted after
        temp_dir = Path("temp_audio")
        temp_dir.mkdir(exist_ok=True)
        temp_file = temp_dir / f"{key}.{file.filename.split('.')[-1]}"
        temp_file.write_bytes(file_content)
        audio_uri = str(temp_file)

    # Create meeting record
    meeting = Meeting(
        title=title,
        audio_path=audio_uri,
        email_to=license.email,
        status="queued",
        progress=0,
        step="queued"
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Trigger processing
    try:
        background.add_task(
            process_meeting,
            meeting_id=meeting.id,
            language=language,
            hints=hints
        )
    except TypeError:
        background.add_task(process_meeting, meeting.id)

    return {
        "ok": True, 
        "meeting_id": meeting.id, 
        "audio_uri": audio_uri,
        "tier": tier,
        "cloud_storage": tier in ("professional", "business")
    }

@router.post("/presign-upload", response_model=PresignUploadOut)
def presign_upload(
    body: PresignUploadIn,
    license_info: tuple = Depends(require_license),
    db: Session = Depends(get_session)
):
    """
    Step 1 (Professional/Business):
    Client asks for a presigned PUT URL for direct Backblaze upload.
    """
    license, tier_config = license_info
    tier = license.tier.lower()

    if tier not in ("professional", "business"):
        raise HTTPException(403, "Cloud uploads require Professional or Business plan")

    # Quota check
    track_meeting_usage(db, license.license_key)

    filename = body.filename or "audio"
    ctype = body.content_type or (mimetypes.guess_type(filename)[0] or "application/octet-stream")
    key = _key_for(license.license_key, tier, filename)

    s3 = s3_client()
    expires_in = 15 * 60  # 15 minutes
    upload_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": S3_BUCKET, "Key": key, "ContentType": ctype},
        ExpiresIn=expires_in,
    )
    return PresignUploadOut(upload_url=upload_url, key=key, expires_in=expires_in)


@router.post("/confirm-upload")
def confirm_upload(
    body: ConfirmUploadIn,
    background: BackgroundTasks,
    license_info: tuple = Depends(require_license),
    db: Session = Depends(get_session)
):
    """
    Step 2:
    After client PUTs file to Backblaze, this endpoint:
      1) Validates size and quota
      2) Creates Meeting row
      3) Launches processing pipeline
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

    # Track usage (raises if limit reached)
    track_meeting_usage(db, license.license_key)

    # Create meeting record
    audio_uri = f"s3://{S3_BUCKET}/{body.key}"
    meeting = Meeting(
        title=body.title or Path(body.key).name,
        audio_path=audio_uri,
        email_to=body.email_to or license.email,
        status="queued",
        progress=0,
        step="queued"
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Trigger pipeline in background
    try:
        background.add_task(
            process_meeting,
            meeting_id=meeting.id,
            language=body.language,
            hints=body.hints,
            compute_type=body.compute_type
        )
    except TypeError:
        background.add_task(process_meeting, meeting.id)

    return {"ok": True, "meeting_id": meeting.id, "audio_uri": audio_uri}


@router.get("/presign-download", response_model=PresignDownloadOut)
def presign_download(
    key: str,
    license_info: tuple = Depends(require_license),
    db: Session = Depends(get_session)
):
    """
    Step 3:
    Generate a short-lived presigned GET URL for secure playback/download.
    Ensures the license owns this file.
    """
    license, tier_config = license_info
    s3_uri = f"s3://{S3_BUCKET}/{key}"

    # Verify ownership — meeting must belong to this license/email
    owned = db.exec(
        select(Meeting).where(Meeting.audio_path == s3_uri, Meeting.email_to == license.email)
    ).first()
    if not owned:
        raise HTTPException(403, "Not allowed to access this file")

    s3 = s3_client()
    expires_in = 15 * 60  # 15 minutes
    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )
    return PresignDownloadOut(url=url, expires_in=expires_in)
