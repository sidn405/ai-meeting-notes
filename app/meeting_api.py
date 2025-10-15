# meeting_api.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from db import SessionLocal, Upload

router = APIRouter(prefix="/meetings", tags=["meetings"])

class CreateAsset(BaseModel):
    s3_key: str
    filename: str
    type: str = "audio"           # "audio" | "video" | "file"
    content_type: str | None = None
    size_bytes: int | None = None
    duration_ms: int | None = None

@router.post("/{meeting_id}/assets")
def create_asset(meeting_id: str, body: CreateAsset):
    with SessionLocal() as db:
        # prevent duplicates by key
        exists = db.scalar(select(Upload).where(Upload.s3_key == body.s3_key))
        if exists:
            return {
                "id": exists.id,
                "meeting_id": exists.meeting_id,
                "s3_key": exists.s3_key,
                "filename": exists.filename,
                "type": exists.type,
                "content_type": exists.content_type,
                "size_bytes": exists.size_bytes,
                "duration_ms": exists.duration_ms,
                "created_at": exists.created_at.isoformat(),
                "duplicate": True,
            }

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
        return {
            "id": row.id,
            "meeting_id": row.meeting_id,
            "s3_key": row.s3_key,
            "filename": row.filename,
            "type": row.type,
            "content_type": row.content_type,
            "size_bytes": row.size_bytes,
            "duration_ms": row.duration_ms,
            "created_at": row.created_at.isoformat(),
        }

@router.get("/{meeting_id}/assets")
def list_assets(meeting_id: str):
    with SessionLocal() as db:
        rows = db.scalars(select(Upload).where(Upload.meeting_id == meeting_id).order_by(Upload.created_at.desc())).all()
        return [
            {
                "id": r.id,
                "meeting_id": r.meeting_id,
                "s3_key": r.s3_key,
                "filename": r.filename,
                "type": r.type,
                "content_type": r.content_type,
                "size_bytes": r.size_bytes,
                "duration_ms": r.duration_ms,
                "created_at": r.created_at.isoformat(),
            } for r in rows
        ]
