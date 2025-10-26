# app/services/pipeline.py
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional
from datetime import datetime
import httpx
from openai import OpenAI
from sqlmodel import select
from sqlalchemy import text as sql_text
import re
from ..db import get_session, DATA_DIR
from ..models import Meeting, License
from ..utils.storage import save_text

# ---------- ASR (AssemblyAI) ----------

def _aai_upload(local_path: str, api_key: str) -> str:
    """
    Uploads a local file to AssemblyAI and returns a temporary URL.
    """
    headers = {"authorization": api_key}
    url = "https://api.assemblyai.com/v2/upload"

    def _iter_chunks(fp, chunk_size=5 * 1024 * 1024):
        while True:
            data = fp.read(chunk_size)
            if not data:
                break
            yield data

    with open(local_path, "rb") as f:
        r = httpx.post(url, headers=headers, content=_iter_chunks(f), timeout=None)
    r.raise_for_status()
    # API returns {"upload_url": "..."} (older responses may use "url")
    j = r.json()
    return j.get("upload_url") or j.get("url")

def _aai_transcribe(audio_path: str, *, language: Optional[str], hints: Optional[str]) -> str:
    """
    Create/poll a transcription job and return the transcript text.
    """
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise RuntimeError("ASSEMBLYAI_API_KEY is not set")

    # ✅ Log file info
    file_size = Path(audio_path).stat().st_size / (1024 * 1024)  # MB
    print(f"📁 Uploading audio: {audio_path} ({file_size:.2f}MB)")

    audio_url = _aai_upload(audio_path, api_key)
    print(f"✅ Upload complete: {audio_url}")

    payload: dict = {"audio_url": audio_url}
    if language:
        payload["language_code"] = language.strip()

    if hints:
        wb = [w.strip() for w in hints.replace("\n", ",").split(",") if w.strip()]
        if wb:
            payload["word_boost"] = wb
            payload["boost_param"] = "high"

    headers = {"authorization": api_key, "content-type": "application/json"}
    create = httpx.post(
        "https://api.assemblyai.com/v2/transcript",
        headers=headers,
        json=payload,
        timeout=None,
    )
    create.raise_for_status()
    tid = create.json()["id"]
    print(f"🎯 Transcription job created: {tid}")

    # Poll until done
    poll_count = 0
    while True:
        poll_count += 1
        res = httpx.get(
            f"https://api.assemblyai.com/v2/transcript/{tid}", 
            headers=headers, 
            timeout=None
        )
        res.raise_for_status()
        j = res.json()
        status = j.get("status")
        
        # ✅ Log polling status
        if poll_count % 5 == 0:  # Every 15 seconds
            print(f"⏳ Poll #{poll_count}: status={status}")
        
        if status == "completed":
            # ✅ Get full response for debugging
            full_response = _debug_aai_response(tid, api_key)
            
            transcript_text = j.get("text", "")
            
            # ✅ CRITICAL: Check full response
            print(f"\n{'='*60}")
            print(f"✅ Transcription Complete!")
            print(f"{'='*60}")
            print(f"Transcript ID: {tid}")
            print(f"Text length: {len(transcript_text)} characters")
            print(f"Word count: {len(transcript_text.split())}")
            print(f"Audio duration: {j.get('audio_duration', 'unknown')} seconds")
            print(f"Confidence: {j.get('confidence', 'unknown')}")
            print(f"\nFirst 300 chars:\n{transcript_text[:300]}")
            print(f"\nLast 300 chars:\n{transcript_text[-300:]}")
            print(f"{'='*60}\n")
            
            # ✅ Check if transcript seems truncated
            if transcript_text and not transcript_text[-1] in '.!?':
                print("⚠️  WARNING: Transcript may be incomplete (doesn't end with punctuation)")
            
            if len(transcript_text) < 100:
                print("⚠️  WARNING: Transcript is very short!")
            
            return transcript_text
            
        if status == "error":
            error_msg = j.get('error', 'Unknown error')
            print(f"❌ AssemblyAI error: {error_msg}")
            raise RuntimeError(f"AssemblyAI error: {error_msg}")
            
        time.sleep(3)
        
def _debug_aai_response(tid: str, api_key: str):
    """Debug helper to see full AssemblyAI response"""
    headers = {"authorization": api_key}
    res = httpx.get(f"https://api.assemblyai.com/v2/transcript/{tid}", headers=headers)
    res.raise_for_status()
    
    response_json = res.json()
    
    print("\n" + "="*60)
    print("FULL ASSEMBLYAI RESPONSE:")
    print("="*60)
    print(json.dumps(response_json, indent=2))
    print("="*60 + "\n")
    
    return response_json

# ---------- LLM summary (OpenAI) ----------

def _summarize_with_openai(transcript: str, title: str) -> dict:
    """
    Return a JSON structure with executive_summary, key_decisions, action_items.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    sys = (
        "You produce concise business meeting notes in JSON. "
        "Fields: executive_summary (string), key_decisions (array of strings), "
        "action_items (array of objects with owner, task, due_date [YYYY-MM-DD or empty], priority [High/Medium/Low]). "
        "Be faithful to the transcript; do not invent details."
    )
    user = f"Title: {title}\n\nTranscript:\n{transcript}"

    resp = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
        temperature=0.2,
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)

# ---------- Email (Resend) ----------

def _email_with_resend_by_id(meeting_id: int, summary_json: dict, summary_path: str, override_to: str):
    """Send the formatted email using Resend. No-op if config isn't present."""
    service = os.getenv("EMAIL_SERVICE", "resend").lower()
    if service != "resend":
        return

    api = os.getenv("EMAIL_API_KEY")
    from_email = os.getenv("FROM_EMAIL")
    from_name = os.getenv("FROM_NAME", "Clipnote")
    
    if not api or not from_email or not override_to:
        return

    # Get meeting title from database in a new session
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            return
        meeting_title = m.title

    app_base = os.getenv("APP_BASE_URL", "").rstrip("/")
    links = ""
    if app_base:
        links = (
            f'<p><a href="{app_base}/meetings/{meeting_id}/download/summary">Download summary (JSON)</a> · '
            f'<a href="{app_base}/meetings/{meeting_id}/download/transcript">Download transcript (TXT)</a></p>'
        )

    ex = summary_json.get("executive_summary", "") or ""
    dec = summary_json.get("key_decisions", []) or []
    ai  = summary_json.get("action_items", []) or []

    # Build action items HTML
    action_html = ""
    for item in ai:
        owner = item.get("owner", "Unassigned")
        task = item.get("task", "")
        due = item.get("due_date", "")
        priority = item.get("priority", "Medium")
        
        priority_color = {
            "High": "#ef4444",
            "Medium": "#f59e0b",
            "Low": "#10b981"
        }.get(priority, "#6b7280")
        
        due_text = f" · Due: {due}" if due else ""
        
        action_html += f'''
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                <div style="margin-bottom: 4px;">
                    <span style="display: inline-block; padding: 2px 8px; background: {priority_color}; color: white; border-radius: 4px; font-size: 11px; font-weight: 600; margin-right: 8px;">{priority}</span>
                    <span style="color: #6b7280; font-size: 14px;">{owner}{due_text}</span>
                </div>
                <div style="color: #111827; font-size: 15px;">{task}</div>
            </td>
        </tr>
        '''

    # Build decisions HTML
    decisions_html = ""
    for decision in dec:
        decisions_html += f'''
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                <div style="color: #111827; font-size: 15px; line-height: 1.5;">• {decision}</div>
            </td>
        </tr>
        '''

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
        <table role="presentation" style="width: 100%; border-collapse: collapse;">
            <tr>
                <td align="center" style="padding: 40px 20px;">
                    <table role="presentation" style="max-width: 600px; width: 100%; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="padding: 32px 32px 24px; border-bottom: 1px solid #e5e7eb;">
                                <h1 style="margin: 0; font-size: 24px; font-weight: 700; color: #111827;">Meeting Summary</h1>
                                <p style="margin: 8px 0 0; font-size: 16px; color: #6b7280;">{meeting_title}</p>
                            </td>
                        </tr>
                        
                        <!-- Executive Summary -->
                        <tr>
                            <td style="padding: 24px 32px;">
                                <h2 style="margin: 0 0 12px; font-size: 18px; font-weight: 600; color: #111827;">Executive Summary</h2>
                                <p style="margin: 0; font-size: 15px; line-height: 1.6; color: #374151;">{ex}</p>
                            </td>
                        </tr>
                        
                        <!-- Key Decisions -->
                        {"" if not dec else f'''
                        <tr>
                            <td style="padding: 24px 32px; border-top: 1px solid #e5e7eb;">
                                <h2 style="margin: 0 0 12px; font-size: 18px; font-weight: 600; color: #111827;">Key Decisions</h2>
                                <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                    {decisions_html}
                                </table>
                            </td>
                        </tr>
                        '''}
                        
                        <!-- Action Items -->
                        {"" if not ai else f'''
                        <tr>
                            <td style="padding: 24px 32px; border-top: 1px solid #e5e7eb;">
                                <h2 style="margin: 0 0 12px; font-size: 18px; font-weight: 600; color: #111827;">Action Items</h2>
                                <table role="presentation" style="width: 100%; border-collapse: collapse; background: #f9fafb; border-radius: 6px; overflow: hidden;">
                                    {action_html}
                                </table>
                            </td>
                        </tr>
                        '''}
                        
                        <!-- Downloads -->
                        {f'''
                        <tr>
                            <td style="padding: 24px 32px; border-top: 1px solid #e5e7eb;">
                                <p style="margin: 0 0 12px; font-size: 14px; color: #6b7280;">Download full documents:</p>
                                <a href="{app_base}/meetings/{meeting_id}/download/summary" style="display: inline-block; margin-right: 12px; padding: 10px 20px; background: #3b82f6; color: white; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 500;">Summary (JSON)</a>
                                <a href="{app_base}/meetings/{meeting_id}/download/transcript" style="display: inline-block; padding: 10px 20px; background: #10b981; color: white; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 500;">Transcript (TXT)</a>
                            </td>
                        </tr>
                        ''' if app_base else ''}
                        
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 24px 32px; border-top: 1px solid #e5e7eb; background: #f9fafb;">
                                <p style="margin: 0; font-size: 13px; color: #6b7280; text-align: center;">
                                    Sent by {from_name}
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    payload = {
        "from": f"{from_name} <{from_email}>",
        "to": [override_to],
        "subject": f"Meeting Summary: {meeting_title}",
        "html": html,
    }

    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        print(f"✅ Email sent to {override_to}")
    except Exception as e:
        print(f"❌ Email error: {e}")

def send_summary_email(meeting_id: int, summary_json: dict, summary_path: str, email_to: str):
    """Wrapper for backward compatibility"""
    _email_with_resend_by_id(meeting_id, summary_json, summary_path, email_to)

# ---------- Progress tracking ----------

def _set_progress(meeting_id: int, percent: int, step: str, status: str = "processing"):
    """Update meeting progress in database"""
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if m:
            m.progress = percent
            m.step = step
            m.status = status
            s.add(m)
            s.commit()

def _get_transcript_path(mid: int, title: str) -> str:
    """Get standardized transcript path"""
    transcripts_dir = DATA_DIR / "transcripts"
    transcripts_dir.mkdir(exist_ok=True, parents=True)
    
    # Sanitize title
    safe_title = re.sub(r'[^\w\s-]', '', title)[:50]
    safe_title = re.sub(r'[-\s]+', '_', safe_title)
    
    filename = f"{mid}_{safe_title}.txt"
    path = transcripts_dir / filename
    
    print(f"📝 Transcript path: {path}")
    return str(path.resolve())

def _get_summary_path(mid: int, title: str) -> str:
    """Get standardized summary path"""
    summaries_dir = DATA_DIR / "summaries"
    summaries_dir.mkdir(exist_ok=True, parents=True)
    
    # Sanitize title
    safe_title = re.sub(r'[^\w\s-]', '', title)[:50]
    safe_title = re.sub(r'[-\s]+', '_', safe_title)
    
    filename = f"{mid}_{safe_title}.json"
    path = summaries_dir / filename
    
    print(f"📊 Summary path: {path}")
    return str(path.resolve())

# ---------- B2 UPLOAD AND CLEANUP ----------

def _get_meeting_tier(meeting_id: int, db) -> str:
    """
    Get the tier for a meeting by looking up associated license.
    Returns: 'free', 'starter', 'professional', or 'business'
    """
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        return "free"
    
    # If meeting has license_id stored, fetch license
    if hasattr(meeting, 'license_id') and meeting.license_id:
        license = db.get(License, meeting.license_id)
        if license:
            return license.tier.lower()
    
    # If meeting has license relationship loaded
    if hasattr(meeting, 'license') and meeting.license:
        return meeting.license.tier.lower()
    
    # Default to free
    return "free"

def _upload_to_b2_and_cleanup(meeting_id: int):
    """
    Upload transcript/summary to B2 for Pro/Business tiers.
    Set status to ready_for_download for Free/Starter.
    Always cleanup media file.
    """
    with get_session() as db:
        meeting = db.get(Meeting, meeting_id)
        if not meeting:
            print(f"❌ Meeting {meeting_id} not found")
            return
        
        # FIX: Use helper function to get tier
        tier = _get_meeting_tier(meeting_id, db)
        
        print(f"\n{'='*60}")
        print(f"🎯 Finalizing meeting {meeting_id} for {tier} tier")
        print(f"{'='*60}")
        
        try:
            # For Pro/Business: Upload to B2
            if tier in ('professional', 'business'):
                print(f"☁️ Uploading transcript and summary to B2...")
                _upload_files_to_b2(meeting_id, db)
            else:
                # For Free/Starter: Set ready for download
                print(f"📱 Setting status for device download...")
                meeting.status = "ready_for_download"
                meeting.step = "Processing complete. Ready to save to your device."
                db.add(meeting)
                db.commit()
                print(f"✅ Meeting ready for auto-download to device")
            
            # Always cleanup media file (audio/video)
            print(f"🗑️ Cleaning up media file...")
            _cleanup_media_file(meeting_id, db)
            
            print(f"✅ Meeting {meeting_id} finalized successfully")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ Finalization error: {e}")
            meeting.status = "failed"
            meeting.step = f"Finalization failed: {str(e)}"
            db.add(meeting)
            db.commit()
            raise

def _upload_files_to_b2(meeting_id: int, db):
    """Upload transcript and summary to B2 cloud storage"""
    from ..routers.storage_b2 import s3_client, get_bucket
    
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        return
    
    s3 = s3_client()
    bucket = get_bucket()
    
    # FIX: Use helper function to get tier
    tier_folder = _get_meeting_tier(meeting_id, db)
    
    # Upload transcript
    if meeting.transcript_path and Path(meeting.transcript_path).exists():
        transcript_key = f"{tier_folder}/transcripts/transcript_{meeting_id}.txt"
        
        with open(meeting.transcript_path, 'rb') as f:
            s3.upload_fileobj(f, bucket, transcript_key)
        
        print(f"  ✅ Transcript uploaded to B2: {transcript_key}")
        
        # Update to B2 path and delete local
        old_path = meeting.transcript_path
        meeting.transcript_path = f"s3://{bucket}/{transcript_key}"
        Path(old_path).unlink()
        print(f"  🗑️ Local transcript deleted: {old_path}")
    
    # Upload summary
    if meeting.summary_path and Path(meeting.summary_path).exists():
        summary_key = f"{tier_folder}/summaries/summary_{meeting_id}.json"
        
        with open(meeting.summary_path, 'rb') as f:
            s3.upload_fileobj(f, bucket, summary_key)
        
        print(f"  ✅ Summary uploaded to B2: {summary_key}")
        
        # Update to B2 path and delete local
        old_path = meeting.summary_path
        meeting.summary_path = f"s3://{bucket}/{summary_key}"
        Path(old_path).unlink()
        print(f"  🗑️ Local summary deleted: {old_path}")
    
    # Update status
    meeting.status = "delivered"
    meeting.step = "Complete. Files stored in cloud."
    db.add(meeting)
    db.commit()

def _cleanup_media_file(meeting_id: int, db):
    """Delete audio/video file after processing (all tiers)"""
    meeting = db.get(Meeting, meeting_id)
    if not meeting or not meeting.audio_path:
        return
    
    try:
        if meeting.audio_path.startswith("s3://"):
            # Pro/Business - delete from B2
            from ..routers.storage_b2 import s3_client, get_bucket
            s3 = s3_client()
            bucket = get_bucket()
            
            key = meeting.audio_path.replace(f"s3://{bucket}/", "")
            
            if "/temp/" in key:
                s3.delete_object(Bucket=bucket, Key=key)
                print(f"  🗑️ Media deleted from B2: {key}")
        else:
            # Free/Starter - delete local file
            media_file = Path(meeting.audio_path)
            if media_file.exists():
                media_file.unlink()
                print(f"  🗑️ Local media deleted: {media_file}")
        
        # Clear media path
        meeting.audio_path = None
        db.add(meeting)
        db.commit()
        
    except Exception as e:
        print(f"  ⚠️ Failed to cleanup media: {e}")

# ---------- MAIN PROCESSING FUNCTIONS ----------

def process_meeting(meeting_id: int, *, language: str | None = None, hints: str | None = None) -> None:
    """Process meeting with transcript AND summary"""
    _set_progress(meeting_id, 5, step="Starting", status="processing")

    # Get initial meeting data
    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise RuntimeError(f"Meeting {meeting_id} not found")
        
        meeting_title = m.title
        audio_path = m.audio_path
        transcript_path = m.transcript_path
        email_to = m.email_to

    try:
        transcript_text = ""
        
        # Step 1: Get or create transcript
        if transcript_path and Path(transcript_path).exists():
            _set_progress(meeting_id, 10, step="Reading transcript")
            transcript_text = Path(transcript_path).read_text(encoding="utf-8")
        elif audio_path and Path(audio_path).exists():
            _set_progress(meeting_id, 20, step="Uploading audio")
            transcript_text = _aai_transcribe(audio_path, language=language, hints=hints)
            
            if not transcript_text or len(transcript_text) < 50:
                raise RuntimeError(f"Transcript too short: {len(transcript_text)} characters")
            
            _set_progress(meeting_id, 60, step="Saving transcript")
            tpath = _get_transcript_path(meeting_id, meeting_title)
            Path(tpath).write_text(transcript_text, encoding="utf-8")
            
            with get_session() as s:
                mm = s.get(Meeting, meeting_id)
                mm.transcript_path = tpath
                s.add(mm)
                s.commit()
                transcript_path = tpath
        else:
            raise RuntimeError("No transcript or audio found.")

        # Step 2: Summarize
        _set_progress(meeting_id, 75, step="Summarizing")
        summary_json = _summarize_with_openai(transcript_text, meeting_title)

        spath = _get_summary_path(meeting_id, meeting_title)
        Path(spath).write_text(json.dumps(summary_json, indent=2), encoding="utf-8")

        with get_session() as s:
            mm = s.get(Meeting, meeting_id)
            mm.summary_path = spath
            s.add(mm)
            s.commit()

        # Step 3: Email if configured
        _set_progress(meeting_id, 90, step="Emailing (if configured)")
        if email_to:
            _email_with_resend_by_id(meeting_id, summary_json, spath, email_to)

        # Step 4: Upload to B2 (Pro/Business) or prepare for download (Free/Starter)
        _set_progress(meeting_id, 95, step="Finalizing")
        _upload_to_b2_and_cleanup(meeting_id)

    except Exception as e:
        _set_progress(meeting_id, 100, step=f"Error: {str(e)}", status="failed")
        print(f"❌ Process failed: {e}")
        raise
    
def process_meeting_transcribe_only(meeting_id: int, *, language: str | None = None, hints: str | None = None) -> None:
    """Process meeting for transcription ONLY"""
    _set_progress(meeting_id, 5, step="Starting transcription", status="processing")

    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise RuntimeError(f"Meeting {meeting_id} not found")
        
        meeting_title = m.title
        audio_path = m.audio_path
        transcript_path = m.transcript_path

    try:
        transcript_text = ""
        
        if transcript_path and Path(transcript_path).exists():
            _set_progress(meeting_id, 95, step="Transcript already exists")
            _upload_to_b2_and_cleanup(meeting_id)
            return
        
        elif audio_path and Path(audio_path).exists():
            _set_progress(meeting_id, 20, step="Uploading audio to AssemblyAI")
            
            try:
                transcript_text = _aai_transcribe(audio_path, language=language, hints=hints)
                
                if not transcript_text or len(transcript_text) < 50:
                    raise RuntimeError(f"Transcript too short: {len(transcript_text)} characters")
                    
            except Exception as e:
                raise RuntimeError(f"Transcription failed: {str(e)}")
            
            _set_progress(meeting_id, 90, step="Saving transcript")
            
            tpath = _get_transcript_path(meeting_id, meeting_title)
            Path(tpath).write_text(transcript_text, encoding="utf-8")
            
            with get_session() as s:
                mm = s.get(Meeting, meeting_id)
                mm.transcript_path = tpath
                s.add(mm)
                s.commit()
            
            # Finalize
            _set_progress(meeting_id, 95, step="Finalizing")
            _upload_to_b2_and_cleanup(meeting_id)
        else:
            raise RuntimeError("No audio file found for transcription.")

    except Exception as e:
        _set_progress(meeting_id, 100, step=f"Transcription failed: {str(e)}", status="failed")
        print(f"❌ Transcription failed: {e}")
        raise

def process_meeting_transcribe_summarize(meeting_id: int, *, language: str | None = None, hints: str | None = None) -> None:
    """Process meeting for transcription AND summarization"""
    _set_progress(meeting_id, 5, step="Starting", status="processing")

    with get_session() as s:
        m = s.get(Meeting, meeting_id)
        if not m:
            raise RuntimeError(f"Meeting {meeting_id} not found")
        
        meeting_title = m.title
        audio_path = m.audio_path
        transcript_path = m.transcript_path
        email_to = m.email_to

    try:
        transcript_text = ""
        
        # Step 1: Transcribe
        if transcript_path and Path(transcript_path).exists():
            _set_progress(meeting_id, 20, step="Reading existing transcript")
            transcript_text = Path(transcript_path).read_text(encoding="utf-8")
        elif audio_path and Path(audio_path).exists():
            _set_progress(meeting_id, 20, step="Uploading audio to AssemblyAI")
            transcript_text = _aai_transcribe(audio_path, language=language, hints=hints)
            
            if not transcript_text or len(transcript_text) < 50:
                raise RuntimeError(f"Transcript too short: {len(transcript_text)} characters")
            
            _set_progress(meeting_id, 60, step="Saving transcript")
            tpath = _get_transcript_path(meeting_id, meeting_title)
            Path(tpath).write_text(transcript_text, encoding="utf-8")
            
            with get_session() as s:
                mm = s.get(Meeting, meeting_id)
                mm.transcript_path = tpath
                s.add(mm)
                s.commit()
                transcript_path = tpath
        else:
            raise RuntimeError("No audio file found")

        # Step 2: Summarize
        _set_progress(meeting_id, 75, step="Summarizing with AI")
        summary_json = _summarize_with_openai(transcript_text, meeting_title)

        spath = _get_summary_path(meeting_id, meeting_title)
        Path(spath).write_text(json.dumps(summary_json, indent=2), encoding="utf-8")

        with get_session() as s:
            mm = s.get(Meeting, meeting_id)
            mm.summary_path = spath
            s.add(mm)
            s.commit()

        # Step 3: Email if configured
        _set_progress(meeting_id, 90, step="Emailing summary")
        if email_to:
            _email_with_resend_by_id(meeting_id, summary_json, spath, email_to)

        # Step 4: Upload to B2 (Pro/Business) or prepare for download (Free/Starter)
        _set_progress(meeting_id, 95, step="Finalizing")
        _upload_to_b2_and_cleanup(meeting_id)

    except Exception as e:
        _set_progress(meeting_id, 100, step=f"Error: {str(e)}", status="failed")
        print(f"❌ Transcribe+Summarize failed: {e}")
        raise