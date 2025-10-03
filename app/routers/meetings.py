# app/routers/meetings.py
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Depends
from typing import Optional
from ..security import require_auth
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pathlib import Path
from sqlmodel import select
from ..db import get_session, DATA_DIR
from ..models import Meeting
from ..services.asr import transcribe
from ..services.summarizer import summarize
from ..services.slacker import send_slack
from ..utils.text import safe_preview
from ..services.branding import compose_meeting_email_parts
from ..services.emailer import send_email
from ..services.pipeline import process_meeting, send_summary_email
import json, re

router = APIRouter(
    prefix="/meetings",
    tags=["meetings"],
    dependencies=[Depends(require_auth)],
)

def _truthy(v) -> bool:
    """Helper to check if form value is truthy"""
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


async def process_meeting(
    meeting_id: int,
    language: str | None = None,
    hints: str | None = None,
    model_size: str | None = None,
    device: str | None = None,
    compute_type: str | None = None
):
    """Main processing pipeline - transcribe, summarize, deliver"""
    with get_session() as s:
        m = s.exec(select(Meeting).where(Meeting.id == meeting_id)).one()
        
        # 1) ASR (only if we have audio)
        if m.audio_path:
            transcript = await transcribe(
                m.audio_path,
                language=language,
                initial_prompt=hints,
                model_size=model_size,
                device=device,
                compute_type=compute_type
            )
            tpath = Path(m.audio_path).with_suffix(".transcript.txt")
            tpath.write_text(transcript, encoding="utf-8")
            m.transcript_path = str(tpath)
            m.status = "transcribed"
            s.add(m)
            s.commit()
        elif m.transcript_path:
            # Read existing transcript
            transcript = Path(m.transcript_path).read_text(encoding="utf-8")
        else:
            raise ValueError("Meeting has no audio or transcript")

        # 2) Summarize
        summary = await summarize(transcript, m.title)
        spath = (Path(m.audio_path) if m.audio_path else Path(m.transcript_path)).with_suffix(".summary.json")
        spath.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        m.summary_path = str(spath)
        m.status = "summarized"
        s.add(m)
        s.commit()

        # 3) Deliver
        body_text_raw = summary.get("summary", "")

        # Build branded subject/plain/html + attach transcript & summary
        attach_paths = []
        if m.transcript_path:
            attach_paths.append(m.transcript_path)
        if m.summary_path:
            attach_paths.append(m.summary_path)

        subject, body_text, body_html, attachments = compose_meeting_email_parts(
            meeting_title=m.title,
            summary_text=body_text_raw,
            meeting_id=m.id,
            attach_paths=attach_paths,
        )

        if m.email_to:
            send_email(m.email_to, subject, body_text, body_html=body_html, attachments=attachments)
        
        send_slack(f"*{m.title}* meeting summarized.\n\n{safe_preview(body_text)}")
        
        m.status = "delivered"
        s.add(m)
        s.commit()
        
# --- status JSON (for polling the progress bar) ---
@router.get("/{meeting_id}/status")
def meeting_status(meeting_id: int):
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(404, "Not found")
        return {
            "id": m.id,
            "title": m.title,
            "status": m.status,
            "progress": m.progress or 0,
            "step": m.step,
            "has_transcript": bool(m.transcript_path),
            "has_summary": bool(m.summary_path),
        }

# --- send email from the results page ---
@router.post("/{meeting_id}/email")
def email_results(meeting_id: int, to: str = Form(...)):
    try:
        send_summary_email(meeting_id, to)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))

# --- simple customer display page ---
@router.get("/{meeting_id}/view", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
def meeting_view(meeting_id: int):
    return f"""
<!doctype html>
<meta charset="utf-8" />
<title>Meeting #{meeting_id} • AI Meeting Notes</title>
<meta name="viewport" content="width=device-width,initial-scale=1" />
<style>
  body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;margin:32px}}
  .card{{border:1px solid #ddd;border-radius:12px;padding:16px;margin-bottom:18px}}
  .bar{{height:14px;background:#eee;border-radius:8px;overflow:hidden}}
  .bar>div{{height:100%;background:#111;width:0%}}
  pre{{white-space:pre-wrap;background:#0b1020;color:#e6edff;padding:12px;border-radius:10px;max-height:400px;overflow:auto}}
  label,input,button{{font:inherit}} input{{padding:8px;width:100%}} button{{background:#111;color:#fff;border:none;border-radius:10px;padding:10px 16px;cursor:pointer}}
  .row{{display:grid;grid-template-columns:1fr 160px;gap:10px;align-items:center}}
</style>

<h1>Meeting #{meeting_id}</h1>

<div class="card">
  <div class="row">
    <div>
      <div id="title" style="font-weight:600"></div>
      <div id="status" style="color:#666;margin-top:6px"></div>
    </div>
    <button id="run" style="display:none">Run now</button>
  </div>
  <div class="bar" style="margin-top:12px"><div id="p"></div></div>
</div>

<div id="results" class="card" style="display:none">
  <h3>Summary</h3>
  <pre id="summary">Loading…</pre>

  <h3 style="margin-top:16px">Send to email</h3>
  <form id="emailForm">
    <div class="row">
      <input name="to" id="to" placeholder="customer@domain.com" type="email" required />
      <button type="submit">Send</button>
    </div>
    <div id="emailOk" style="color:#16a34a;margin-top:8px;display:none">Sent ✓</div>
    <div id="emailErr" style="color:#b91c1c;margin-top:8px;display:none"></div>
  </form>

  <p style="margin-top:10px">
    <a id="dlSum" href="#">Download summary (JSON)</a> ·
    <a id="dlTxt" href="#">Download transcript (TXT)</a>
  </p>
</div>

<script>
const id = {meeting_id};

async function getStatus() {{
  const r = await fetch(`/meetings/${{id}}/status`);
  if (!r.ok) throw new Error('status error');
  return r.json();
}}

async function getSummary() {{
  const r = await fetch(`/meetings/${{id}}/download/summary`);
  if (!r.ok) throw new Error('no summary yet');
  return r.text();
}}

async function tick() {{
  try {{
    const s = await getStatus();
    document.getElementById('title').textContent = s.title || `Meeting #${{id}}`;
    document.getElementById('status').textContent = `${{s.status}}${{s.step ? ' — '+s.step : ''}}`;
    document.getElementById('p').style.width = (s.progress||0) + '%';
    // show Run Now if queued
    document.getElementById('run').style.display = (s.status || '').startsWith('queued') ? '' : 'none';

    if ((s.status||'').startsWith('delivered')) {{
      document.getElementById('results').style.display = '';
      // download links
      document.getElementById('dlSum').href = `/meetings/${{id}}/download/summary`;
      document.getElementById('dlTxt').href = `/meetings/${{id}}/download/transcript`;
      // fetch summary pretty json once
      if (!document.getElementById('summary').dataset.loaded) {{
        try {{
          const txt = await getSummary();
          document.getElementById('summary').textContent = txt;
          document.getElementById('summary').dataset.loaded = '1';
        }} catch (e) {{}}
      }}
      return; // stop polling once delivered
    }}
  }} catch (e) {{}}
  setTimeout(tick, 2000);
}}

document.getElementById('run').onclick = async () => {{
  const r = await fetch(`/meetings/${{id}}/run`, {{ method: 'POST' }});
  await r.json();
  setTimeout(tick, 500);
}};

document.getElementById('emailForm').onsubmit = async (e) => {{
  e.preventDefault();
  const fd = new FormData(e.target);
  const r = await fetch(`/meetings/${{id}}/email`, {{ method: 'POST', body: fd }});
  document.getElementById('emailOk').style.display = r.ok ? '' : 'none';
  document.getElementById('emailErr').style.display = r.ok ? 'none' : '';
  if (!r.ok) document.getElementById('emailErr').textContent = (await r.text()) || 'Send failed';
}};

tick();
</script>
"""


@router.post("/upload")
async def upload_meeting(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    email_to: str | None = Form(None),
    file: UploadFile = File(...),
    language: str | None = Form(None),
    hints: str | None = Form(None),
    model_size: str | None = Form(None),
    device: str | None = Form(None),
    compute_type: str | None = Form(None),
):
    """Upload audio/video file and queue for processing"""
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".m4a", ".wav", ".mp4"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    audio_path = DATA_DIR / f"{Path(file.filename).stem}.uploaded{ext}"
    audio_path.write_bytes(await file.read())

    with get_session() as s:
        m = Meeting(title=title, audio_path=str(audio_path), email_to=email_to)
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Queue the processing as a background task
    background_tasks.add_task(
        process_meeting,
        mid,
        language,
        hints,
        model_size,
        device,
        compute_type
    )
    
    return {"id": mid, "status": "queued"}


@router.post("/upload-sync")
async def upload_meeting_sync(
    title: str = Form(...),
    email_to: str | None = Form(None),
    file: UploadFile = File(...),
    language: str | None = Form(None),
    hints: str | None = Form(None),
    model_size: str | None = Form(None),
    device: str | None = Form(None),
    compute_type: str | None = Form(None),
):
    """Upload and process immediately (blocks until complete)"""
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp3", ".m4a", ".wav", ".mp4"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    audio_path = DATA_DIR / f"{Path(file.filename).stem}.uploaded{ext}"
    audio_path.write_bytes(await file.read())

    with get_session() as s:
        m = Meeting(title=title, audio_path=str(audio_path), email_to=email_to)
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Process immediately and wait
    await process_meeting(mid, language, hints, model_size, device, compute_type)

    with get_session() as s:
        m = s.get(Meeting, mid)
        if not m:
            raise HTTPException(404, "Not found")
        return {"id": m.id, "status": m.status}


@router.post("/from-text")
async def create_from_text(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: str | None = Form(None),
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
            status="queued"
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        mid = m.id

    # Process immediately (text-only is fast)
    await process_meeting(mid)

    with get_session() as s:
        m = s.get(Meeting, mid)
        return {"id": m.id, "status": m.status}


@router.post("/from-text-sync")
async def create_from_text_sync(
    title: str = Form(...),
    transcript: str = Form(...),
    email_to: str | None = Form(None),
):
    """Alias for from-text (already synchronous)"""
    return await create_from_text(title, transcript, email_to)


@router.get("/{meeting_id}")
def get_meeting(meeting_id: int):
    """Get meeting details"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(status_code=404, detail="Not found")
        return m


@router.get("/{meeting_id}/download/transcript")
def download_transcript(meeting_id: int):
    """Download meeting transcript"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not (m and m.transcript_path and Path(m.transcript_path).exists()):
            raise HTTPException(status_code=404, detail="Transcript not found")
        return FileResponse(
            m.transcript_path,
            media_type="text/plain",
            filename=Path(m.transcript_path).name
        )


@router.get("/{meeting_id}/download/summary")
def download_summary(meeting_id: int):
    """Download meeting summary"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not (m and m.summary_path and Path(m.summary_path).exists()):
            raise HTTPException(status_code=404, detail="Summary not found")
        return FileResponse(
            m.summary_path,
            media_type="application/json",
            filename=Path(m.summary_path).name
        )


@router.post("/{meeting_id}/run")
async def run_meeting(meeting_id: int):
    """Manually trigger processing for a meeting"""
    await process_meeting(meeting_id)
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise HTTPException(404, "Not found")
        return {"id": m.id, "status": m.status}