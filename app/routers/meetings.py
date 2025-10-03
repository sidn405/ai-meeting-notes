from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Depends
from fastapi.responses import FileResponse

from ..security import require_auth
from ..db import get_session
from ..models import Meeting
from ..utils.storage import save_upload, save_text
from ..services.pipeline import process_meeting


def _truthy(v) -> bool:
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


router = APIRouter(
    prefix="/meetings",
    tags=["meetings"],
    dependencies=[Depends(require_auth)],
)


# -------------------- Upload audio/video --------------------
@router.post("/upload")
def upload_meeting(
    title: str = Form(...),
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    hints: Optional[str] = Form(None),
    email_to: Optional[str] = Form(None),
    slack_channel: Optional[str] = Form(None),
    sync: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None,
):
    run_sync = _truthy(sync)

    # persist upload
    audio_path = save_upload(file)

    with get_session() as s:
        m = Meeting(
            title=title,
            audio_path=audio_path,
            transcript_path=None,
            summary_path=None,
            status="queued",
            email_to=email_to,
            slack_channel=slack_channel,
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    if run_sync:
        # process immediately (blocks until finished)
        process_meeting(mid, language=language, hints=hints)
        with get_session() as s:
            mm = s.get(Meeting, mid)
            return {"id": mm.id, "status": mm.status}
    else:
        if background_tasks is None:
            raise HTTPException(500, "Background tasks unavailable")
        background_tasks.add_task(process_meeting, mid, language, hints)
        return {"id": mid, "status": "queued"}


# -------------------- Create from pasted transcript --------------------
@router.post("/from-text")
def from_text(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: Optional[str] = Form(None),
    slack_channel: Optional[str] = Form(None),
    sync: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None,
):
    run_sync = _truthy(sync)

    # save transcript to a file so users can download later
    transcript_path = save_text(transcript, title=title)

    with get_session() as s:
        m = Meeting(
            title=title,
            audio_path=None,
            transcript_path=transcript_path,
            summary_path=None,
            status="queued",
            email_to=email_to,
            slack_channel=slack_channel,
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    if run_sync:
        process_meeting(mid)  # no language/hints for text path
        with get_session() as s:
            mm = s.get(Meeting, mid)
            return {"id": mm.id, "status": mm.status}
    else:
        if background_tasks is None:
            raise HTTPException(500, "Background tasks unavailable")
        background_tasks.add_task(process_meeting, mid, None, None)
        return {"id": mid, "status": "queued"}


# -------------------- Inspect & downloads --------------------
@router.get("/{meeting_id}")
def get_meeting(meeting_id: int):
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(status_code=404, detail="Not found")
        return m

@router.get("/{meeting_id}/download/transcript")
def download_transcript(meeting_id: int):
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not (m and m.transcript_path and Path(m.transcript_path).exists()):
            raise HTTPException(status_code=404, detail="Transcript not found")
        return FileResponse(
            m.transcript_path,
            media_type="text/plain",
            filename=Path(m.transcript_path).name,
        )

@router.get("/{meeting_id}/download/summary")
def download_summary(meeting_id: int):
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not (m and m.summary_path and Path(m.summary_path).exists()):
            raise HTTPException(status_code=404, detail="Summary not found")
        return FileResponse(
            m.summary_path,
            media_type="application/json",
            filename=Path(m.summary_path).name,
        )


# -------------------- Run a queued job now --------------------
@router.post("/run")
def run_now_form(id: int = Form(...)):
    process_meeting(id)
    with get_session() as s:
        m = s.get(Meeting, id)
        if not m:
            raise HTTPException(404, "Not found")
        return {"id": m.id, "status": m.status}

@router.post("/{meeting_id}/run")
def run_now(meeting_id: int):
    process_meeting(meeting_id)
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(404, "Not found")
        return {"id": m.id, "status": m.status}
