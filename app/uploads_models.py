# app/uploads_models.py
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class Upload(SQLModel, table=True):
    __tablename__ = "uploads"
    id: Optional[int] = Field(default=None, primary_key=True)
    meeting_id: str = Field(index=True, max_length=64)
    s3_key: str = Field(index=True, unique=True, max_length=1024)
    filename: str = Field(max_length=256)
    type: str = Field(max_length=32, description="audio|video|file")
    content_type: Optional[str] = Field(default=None, max_length=128)
    size_bytes: Optional[int] = Field(default=None)
    duration_ms: Optional[int] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
