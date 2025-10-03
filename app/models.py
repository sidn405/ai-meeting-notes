from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Meeting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    audio_path: Optional[str] = None
    transcript_path: Optional[str] = None
    summary_path: Optional[str] = None
    status: str = "uploaded"  # uploaded|transcribed|summarized|delivered
    created_at: datetime = Field(default_factory=datetime.utcnow)
    email_to: Optional[str] = None
    slack_channel: Optional[str] = None
    status: str = "queued"
    # NEW:
    progress: int = 0
    step: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)