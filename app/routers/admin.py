# app/routers/admin.py
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import select, Session
from pathlib import Path
from ..db import get_session, DATA_DIR
from ..models import Meeting

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.delete("/meetings/delete-all")
def delete_all_meetings(db: Session = Depends(get_session)):
    """
    Delete ALL meetings and their files
    Simple endpoint for clearing test data between fresh installs
    """
    meetings = db.exec(select(Meeting)).all()
    deleted_count = 0
    
    for m in meetings:
        # Delete associated files
        try:
            if m.audio_path and Path(m.audio_path).exists():
                Path(m.audio_path).unlink()
            if m.transcript_path and Path(m.transcript_path).exists():
                Path(m.transcript_path).unlink()
            if m.summary_path and Path(m.summary_path).exists():
                Path(m.summary_path).unlink()
        except:
            pass  # Continue even if file deletion fails
        
        db.delete(m)
        deleted_count += 1
    
    db.commit()
    
    return {
        "success": True,
        "deleted": deleted_count,
        "message": f"Deleted {deleted_count} meetings"
    }