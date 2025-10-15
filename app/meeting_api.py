# app/meeting_api.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from sqlmodel import select

from app.db import get_session          # ✅ your db.py exports get_session()
from app.uploads_models import Upload   # ✅ model lives in app/upload_models.py

router = APIRouter(prefix="/meetings", tags=["meetings"])

class CreateAsset(BaseModel):
    s3_key: str
    filename: str
    type: str = "audio"                  # "audio" | "video" | "file"
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    duration_ms: Optional[int] = None

@router.post("/{meeting_id}/assets")
def create_asset(meeting_id: str, body: CreateAsset):
    with get_session() as db:
        # prevent duplicates by key
        existing = db.exec(select(Upload).where(Upload.s3_key == body.s3_key)).first()
        if existing:
            return {**existing.model_dump(), "duplicate": True}

        row = Upload(
            meeting_id=meeting_id,
            s3_key=body.s3_key,
            filename=body.filename,
            type=body.type,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
            duration_ms=body.duration_ms,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

@router.get("/{meeting_id}/assets", response_model=List[Upload])
def list_assets(meeting_id: str):
    with get_session() as db:
        return db.exec(
            select(Upload).where(Upload.meeting_id == meeting_id).order_by(Upload.created_at.desc())
        ).all()
