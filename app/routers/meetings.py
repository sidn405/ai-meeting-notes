# app/routers/meetings.py
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Depends  # <-- add Depends
from typing import Optional
from ..security import require_auth  # <-- import
from fastapi.responses import FileResponse
from pathlib import Path
from sqlmodel import select
from ..db import get_session, DATA_DIR
from ..models import Meeting
from ..services.asr import transcribe
from ..services.summarizer import summarize
from ..db import get_session
from ..models import Meeting
from ..services.slacker import send_slack
from ..utils.text import safe_preview
import json, re, asyncio, mimetypes
from ..services.branding import compose_meeting_email_parts
from ..services.emailer import send_email
from ..utils.storage import save_upload, save_text
from ..services.pipeline import process_meeting   # whatever you named it

router = APIRouter(prefix="/meetings", tags=["meetings"])

router = APIRouter(
    prefix="/meetings",
    tags=["meetings"],
    dependencies=[Depends(require_auth)],   # <-- protect all endpoints in this router
)

@router.post("/upload")
async def upload_meeting(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    email_to: str | None = Form(None),
    file: UploadFile = File(...),
    language: str | None = Form(None),       # e.g., "en"
    hints: str | None = Form(None),          # jargon/terminology
    model_size: str | None = Form(None),     # tiny|base|small|medium|large-v3
    device: str | None = Form(None),         # cpu|cuda
    compute_type: str | None = Form(None),   # int8|float16|float32|auto
):
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".m4a", ".wav", ".mp4"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    audio_path = DATA_DIR / f"{Path(file.filename).stem}.uploaded{ext}"
    audio_path.write_bytes(await file.read())

    with get_session() as s:
        m = Meeting(title=title, audio_path=str(audio_path), email_to=email_to)
        s.add(m); s.commit(); s.refresh(m)

    background_tasks.add_task(_process_meeting_sync, m.id, language, hints, model_size, device, compute_type)
    return {"id": m.id, "status": "queued"}

def _process_meeting_sync(meeting_id: int, language: str | None, hints: str | None,
                          model_size: str | None, device: str | None, compute_type: str | None):
    asyncio.run(process_meeting(meeting_id, language, hints, model_size, device, compute_type))

async def process_meeting(meeting_id: int, language: str | None, hints: str | None,
                          model_size: str | None, device: str | None, compute_type: str | None):
    with get_session() as s:
        m = s.exec(select(Meeting).where(Meeting.id == meeting_id)).one()
        # 1) ASR
        transcript = await transcribe(m.audio_path,
                                      language=language,
                                      initial_prompt=hints,
                                      model_size=model_size,
                                      device=device,
                                      compute_type=compute_type)
        tpath = Path(m.audio_path).with_suffix(".transcript.txt")
        tpath.write_text(transcript, encoding="utf-8")
        m.transcript_path = str(tpath)
        m.status = "transcribed"
        s.add(m); s.commit()

        # 2) Summarize
        summary = await summarize(transcript, m.title)
        spath = Path(m.audio_path).with_suffix(".summary.json")
        spath.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        m.summary_path = str(spath)
        m.status = "summarized"
        s.add(m); s.commit()

        # 3) Deliver
        body_text_raw = summary.get("summary", "")

        # Build branded subject/plain/html + attach transcript & summary
        attach_paths = []
        if m.transcript_path: attach_paths.append(m.transcript_path)
        if m.summary_path:    attach_paths.append(m.summary_path)

        subject, body_text, body_html, attachments = compose_meeting_email_parts(
            meeting_title=m.title,
            summary_text=body_text_raw,
            meeting_id=m.id,
            attach_paths=attach_paths,
        )

        if m.email_to:
            send_email(m.email_to, f"Meeting Notes: {m.title}", body_text, body_html=body_html, attachments=attachments)
        send_slack(f"*{m.title}* meeting summarized.\n\n{safe_preview(body_text)}")
        m.status = "delivered"
        s.add(m); s.commit()
        
def _truthy(v) -> bool:
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


@router.post("/from-text")
async def create_from_text(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: str | None = Form(None),
):
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.strip()) or "meeting"
    tpath = DATA_DIR / f"from_text_{safe_stem}.transcript.txt"
    tpath.write_text(transcript, encoding="utf-8")

    summary = await summarize(transcript, title)
    spath = DATA_DIR / f"from_text_{safe_stem}.summary.json"
    spath.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with get_session() as s:
        m = Meeting(title=title, audio_path="", email_to=email_to,
                    transcript_path=str(tpath), summary_path=str(spath), status="delivered")
        s.add(m); s.commit(); s.refresh(m)

    body = summary.get("summary", "")
    if email_to:
        send_email(email_to, f"Meeting Notes: {title}", body)
    send_slack(f"*{title}* meeting summarized.\n\n{safe_preview(body)}")

    return {"id": m.id, "status": "delivered", "transcript_path": str(tpath), "summary_path": str(spath)}

@router.get("/{meeting_id}")
def get_meeting(meeting_id: int):
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(status_code=404, detail="Not found")
        return m

# ---------- new: download endpoints ----------
@router.get("/{meeting_id}/download/transcript")
def download_transcript(meeting_id: int):
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not (m and m.transcript_path and Path(m.transcript_path).exists()):
            raise HTTPException(status_code=404, detail="Transcript not found")
        return FileResponse(m.transcript_path, media_type="text/plain",
                            filename=Path(m.transcript_path).name)

@router.get("/{meeting_id}/download/summary")
def download_summary(meeting_id: int):
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not (m and m.summary_path and Path(m.summary_path).exists()):
            raise HTTPException(status_code=404, detail="Summary not found")
        return FileResponse(m.summary_path, media_type="application/json",
                            filename=Path(m.summary_path).name)
        
# ---------- from text ----------
@router.post("/meetings/from-text")
def from_text(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: Optional[str] = Form(None),
    slack_channel: Optional[str] = Form(None),
    sync: Optional[str] = Form(None),                # NEW
    background_tasks: BackgroundTasks = None,          # NEW
):
    with get_session() as s:
        m = Meeting(title=title, transcript_path=None, audio_path=None,
                    email_to=email_to, slack_channel=slack_channel, status="queued")
        s.add(m); s.commit(); s.refresh(m)
    # write transcript to a temp file for consistency if your pipeline expects a path
    # or pass transcript text straight into process_meeting depending on your implementation

    if sync:
        process_meeting(m.id)                          # run now
        with get_session() as s:
            m = s.get(Meeting, m.id)
            return {"id": m.id, "status": m.status}
    else:
        if background_tasks is None:
            raise HTTPException(500, "Background tasks unavailable")
        background_tasks.add_task(process_meeting, m.id)
        return {"id": m.id, "status": "queued"}


# ---------- upload audio/video ----------
@router.post("/meetings/upload")
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
    
@router.post("/meetings/run")
def run_now_form(id: int = Form(...)):
    process_meeting(id)
    with get_session() as s:
        m = s.get(Meeting, id)
        if not m:
            raise HTTPException(404, "Not found")
        return {"id": m.id, "status": m.status}

    
@router.post("/meetings/{mid}/run")
def run_now(mid: int):
    process_meeting(mid)
    with get_session() as s:
        m = s.get(Meeting, mid)
        if not m:
            raise HTTPException(404, "Not found")
        return {"id": m.id, "status": m.status}
    
@router.post("/from-text-sync")
def from_text_sync(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: Optional[str] = Form(None),
    slack_channel: Optional[str] = Form(None),
):
    # Save the transcript so it’s downloadable later
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
        s.add(m); s.commit(); s.refresh(m)
        mid = m.id

    # Run the whole pipeline now (blocking)
    process_meeting(mid)

    with get_session() as s:
        m = s.get(Meeting, mid)
        if not m:
            raise HTTPException(404, "Not found")
        return {"id": m.id, "status": m.status}


@router.post("/upload-sync")
def upload_meeting_sync(
    title: str = Form(...),
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    hints: Optional[str] = Form(None),
    email_to: Optional[str] = Form(None),
    slack_channel: Optional[str] = Form(None),
):
    # Persist file
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
        s.add(m); s.commit(); s.refresh(m)
        mid = m.id

    # Run the whole pipeline now (blocking)
    process_meeting(mid, language=language, hints=hints)

    with get_session() as s:
        m = s.get(Meeting, mid)
        if not m:
            raise HTTPException(404, "Not found")
        return {"id": m.id, "status": m.status}

