from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import init_db
from .routers import meetings, health, auth
import os
from fastapi.responses import HTMLResponse
from .services.branding import render_meeting_notes_email_html

os.environ["PATH"] = r"C:\Tools\ffmpeg\bin;" + os.environ["PATH"]


app = FastAPI(title="AI Meeting Notes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/upload-test", response_class=HTMLResponse)
def upload_test():
    return """
    <!doctype html>
    <html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>AI Meeting Notes – Test</title>
    <style>
      body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:40px;max-width:980px}
      input,textarea,select{width:100%;padding:8px} label{display:block;margin:10px 0 4px}
      .row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
      .box{padding:16px;border:1px solid #ddd;border-radius:10px;margin-bottom:28px}
      button{padding:10px 16px;border-radius:10px;background:#111;color:#fff;border:none;cursor:pointer}
      small{color:#555}
    </style></head><body>
    <h1>AI Meeting Notes – Test</h1>

    <div class="box">
      <h2>From Transcript (No Audio)</h2>
      <form action="/meetings/from-text" method="post" target="_blank">
        <label>Title</label><input name="title" required />
        <label>Transcript</label>
        <textarea name="transcript" rows="10" placeholder="Paste transcript here…" required></textarea>
        <label>Email results to (optional)</label><input type="email" name="email_to" />
        <br/><br/><button type="submit">Summarize</button>
      </form>
      <small>Bypasses ASR. Use to test summarizer & delivery.</small>
    </div>

    <div class="box">
      <h2>Upload Meeting (Audio/Video)</h2>
      <form action="/meetings/upload" method="post" enctype="multipart/form-data" target="_blank">
        <div class="row">
          <div><label>Title</label><input name="title" required /></div>
          <div><label>Email results to (optional)</label><input type="email" name="email_to" /></div>
        </div>

        <div class="row">
          <div>
            <label>Language (e.g., en)</label>
            <input name="language" value="en" />
          </div>
          <div>
            <label>Hints / Terminology (comma or newline separated)</label>
            <input name="hints" placeholder="Alice, Bob, OKR, churn, Salesforce, Zendesk" />
          </div>
        </div>

        <div class="row">
          <div>
            <label>Model size</label>
            <select name="model_size">
              <option value="">(use default)</option>
              <option>tiny</option><option>base</option><option selected>small</option>
              <option>medium</option><option>large-v3</option>
            </select>
          </div>
          <div>
            <label>Device</label>
            <select name="device">
              <option value="">(auto)</option>
              <option selected>cpu</option>
              <option>cuda</option>
            </select>
          </div>
        </div>

        <div class="row">
          <div>
            <label>Compute type</label>
            <select name="compute_type">
              <option value="">(auto)</option>
              <option selected>int8</option>
              <option>float16</option>
              <option>float32</option>
            </select>
          </div>
          <div>
            <label>Audio/Video file (.mp3/.m4a/.wav/.mp4)</label>
            <input type="file" name="file" accept="audio/*,video/mp4" required />
          </div>
        </div>

        <br/><button type="submit">Upload & Process</button>
      </form>
      <small>Tip: On CPU, <b>small + int8</b> is a good balance. For accuracy, try <b>medium</b> (slower).</small>
    </div>

    <p>Dev note: Without SMTP/Slack, emails go to <code>data/outbox/email/</code> and Slack logs to <code>data/outbox/slack.log</code>.</p>
    </body></html>
    """
    
@app.get("/_brand_preview", response_class=HTMLResponse)
def brand_preview():
    sample = """Executive Summary
- Revenue up 12% MoM
- Churn stable at 4.2%

Key Decisions
- Launch referral program in October

Action Items
- Alice: finalize email copy by Friday
- Bob: update dashboards by Wednesday
"""
    return render_meeting_notes_email_html(
        meeting_title="Weekly Growth Standup",
        summary_text=sample,
        meeting_id=123,
    )

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/")
def index():
    return {"ok": True, "app": "AI Meeting Notes", "routes": ["/health", "/meetings/upload", "/meetings/from-text", "/meetings/{id}"]}

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(meetings.router)
