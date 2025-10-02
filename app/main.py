from fastapi import FastAPI, Request
from .security import COOKIE_NAME
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
def upload_test(request: Request):
    logged_in = COOKIE_NAME in request.cookies

    login_box = """
      <div class="box">
        <h2>Login</h2>
        <form action="/auth/web-login" method="post">
          <label>Username</label>
          <input name="username" value="admin" required />
          <label>Password</label>
          <input name="password" type="password" required />
          <input type="hidden" name="next_path" value="/upload-test" />
          <br/><br/><button type="submit">Login</button>
        </form>
        <small>After login, the server sets an <b>HttpOnly</b> cookie. Your browser will include it automatically on the forms below.</small>
      </div>
    """

    logout_box = """
      <div class="box">
        <h2>Authenticated</h2>
        <p style="margin:4px 0 12px 0;color:#16a34a">✅ You are logged in. You can submit the forms below.</p>
        <form action="/auth/logout" method="post" style="display:inline">
          <input type="hidden" name="next_path" value="/upload-test" />
          <button type="submit">Logout</button>
        </form>
      </div>
    """

    auth_section = logout_box if logged_in else login_box

    return f"""
    <!doctype html>
    <html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>AI Meeting Notes – Test</title>
    <style>
      body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:40px;max-width:960px}}
      input,textarea{{width:100%;padding:8px}} label{{display:block;margin:10px 0 4px}}
      .row{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
      .box{{padding:16px;border:1px solid #ddd;border-radius:10px;margin-bottom:28px}}
      button{{padding:10px 16px;border-radius:10px;background:#111;color:#fff;border:none;cursor:pointer}}
      small{{color:#555}}
      .muted{{color:#555}}
    </style></head><body>
    <h1>AI Meeting Notes – Test</h1>

    {auth_section}

    <div class="box">
      <h2>From Transcript (No Audio)</h2>
      <p class="muted">This endpoint is protected; after login your browser will include the cookie automatically.</p>
      <form action="/meetings/from-text" method="post" target="_blank">
        <label>Title</label>
        <input name="title" required />
        <label>Transcript</label>
        <textarea name="transcript" rows="10" placeholder="Paste transcript here…" required></textarea>
        <label>Email results to (optional)</label>
        <input type="email" name="email_to" />
        <br/><br/><button type="submit">Summarize</button>
      </form>
    </div>

    <div class="box">
      <h2>Upload Meeting (Audio/Video)</h2>
      <p class="muted">On Railway we recommend cloud ASR (AssemblyAI); no ffmpeg needed in the container.</p>
      <form action="/meetings/upload" method="post" enctype="multipart/form-data" target="_blank">
        <div class="row">
          <div>
            <label>Title</label>
            <input name="title" required />
          </div>
          <div>
            <label>Email results to (optional)</label>
            <input type="email" name="email_to" />
          </div>
        </div>

        <div class="row">
          <div>
            <label>Language (e.g., <code>en</code>)</label>
            <input name="language" value="en" />
          </div>
          <div>
            <label>Hints / Terminology (comma or newline separated)</label>
            <input name="hints" placeholder="Alice, Bob, OKR, churn, Salesforce, Zendesk" />
          </div>
        </div>

        <label>Audio/Video file (.mp3/.m4a/.wav/.mp4)</label>
        <input type="file" name="file" accept="audio/*,video/mp4" required />
        <br/><br/><button type="submit">Upload & Process</button>
      </form>
    </div>

    <p class="muted">Tip: If you’re testing on localhost (http), set <code>COOKIE_SECURE=0</code>. On Railway (https), keep <code>COOKIE_SECURE=1</code>.</p>
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

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return """
<!doctype html><meta charset="utf-8">
<title>Login</title>
<style>
 body{font-family:system-ui;margin:40px;max-width:480px}
 input,button{font:inherit;padding:8px} input{width:100%}
 button{background:#111;color:#fff;border:none;border-radius:8px;padding:10px 16px;margin-top:10px}
</style>
<h1>Login</h1>
<form action="/auth/web-login" method="post">
  <label>Username</label><input name="username" value="admin" required>
  <label>Password</label><input name="password" type="password" required>
  <input type="hidden" name="next_path" value="/upload-test">
  <button type="submit">Login</button>
</form>
<form action="/auth/logout" method="post" style="margin-top:16px">
  <input type="hidden" name="next_path" value="/upload-test">
  <button type="submit">Logout</button>
</form>
<p style="color:#555">After login, the server sets an <b>HttpOnly cookie</b>. Your browser includes it automatically on form submits.</p>
"""

@app.get("/browser-test", response_class=HTMLResponse)
def browser_test():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>AI Meeting Notes — Browser Test</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:32px;max-width:980px}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
    input,textarea,select,button{font:inherit}
    input,textarea,select{width:100%;padding:8px}
    .box{border:1px solid #ddd;border-radius:10px;padding:16px;margin-bottom:24px}
    button{padding:10px 16px;border-radius:10px;background:#111;color:#fff;border:none;cursor:pointer}
    code{background:#f6f7f9;padding:2px 6px;border-radius:6px}
    #out{white-space:pre-wrap;background:#0b1020;color:#d6e1ff;padding:12px;border-radius:8px;min-height:90px}
    small{color:#555}
  </style>
</head>
<body>
  <h1>AI Meeting Notes — Browser Test</h1>

  <div class="box">
    <h2>Auth</h2>
    <div class="row">
      <div>
        <label>API Key (X-API-Key)</label>
        <input id="apiKey" placeholder="paste API_KEYS value (optional)">
      </div>
      <div>
        <label>JWT Bearer Token</label>
        <input id="token" placeholder="paste token or use Login below">
      </div>
    </div>
    <details style="margin-top:10px">
      <summary>Login to get JWT (admin)</summary>
      <div class="row" style="margin-top:8px">
        <input id="u" placeholder="ADMIN_USER" value="admin">
        <input id="p" placeholder="ADMIN_PASSWORD" type="password">
      </div>
      <button onclick="login()">Get Token</button>
      <small style="display:block;margin-top:6px">Sends POST <code>/auth/token</code> and stores token in localStorage.</small>
    </details>
  </div>

  <div class="box">
    <h2>Summarize from Text (no audio)</h2>
    <div class="row">
      <input id="titleTxt" placeholder="Title e.g. Weekly Growth Sync">
      <input id="emailTxt" placeholder="Email results to (optional)">
    </div>
    <textarea id="transcript" rows="10" placeholder="Paste transcript here…"></textarea>
    <div style="margin-top:10px"><button onclick="fromText()">Summarize</button></div>
  </div>

  <div class="box">
    <h2>Upload Audio/Video</h2>
    <div class="row">
      <input id="titleAud" placeholder="Title e.g. Sales Call with Acme">
      <input id="emailAud" placeholder="Email results to (optional)">
    </div>
    <div class="row">
      <input id="lang" placeholder="Language (e.g., en)" value="en">
      <input id="hints" placeholder="Hints/terminology (optional)">
    </div>
    <input id="file" type="file" accept="audio/*,video/mp4" style="margin-top:6px">
    <div style="margin-top:10px"><button onclick="upload()">Upload & Process</button></div>
    <small>On Railway we recommend cloud ASR (AssemblyAI); no ffmpeg needed.</small>
  </div>

  <h3>Response</h3>
  <div id="out">—</div>

<script>
const out = (x) => document.getElementById('out').textContent =
  (typeof x === 'string' ? x : JSON.stringify(x, null, 2));

const saveAuth = () => {
  localStorage.setItem('apiKey', document.getElementById('apiKey').value.trim());
  localStorage.setItem('token',  document.getElementById('token').value.trim());
};
const loadAuth = () => {
  document.getElementById('apiKey').value = localStorage.getItem('apiKey') || "";
  document.getElementById('token').value  = localStorage.getItem('token')  || "";
};
loadAuth();

function authHeaders() {
  const h = {};
  const apiKey = document.getElementById('apiKey').value.trim();
  const tok    = document.getElementById('token').value.trim();
  if (apiKey) h['X-API-Key'] = apiKey;
  else if (tok) h['Authorization'] = 'Bearer ' + tok;
  return h;
}

async function login() {
  try {
    const body = { username: document.getElementById('u').value, password: document.getElementById('p').value };
    const r = await fetch('/auth/token', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
    });
    const j = await r.json();
    if (!r.ok) throw j;
    document.getElementById('token').value = j.access_token || '';
    saveAuth();
    out(j);
  } catch (e) { out(e); }
}

async function fromText() {
  try {
    saveAuth();
    const fd = new URLSearchParams();
    fd.set('title', document.getElementById('titleTxt').value);
    fd.set('transcript', document.getElementById('transcript').value);
    const email = document.getElementById('emailTxt').value.trim();
    if (email) fd.set('email_to', email);

    const r = await fetch('/meetings/from-text', {
      method: 'POST',
      headers: authHeaders(),
      body: fd
    });
    const j = await r.json();
    out(j);
  } catch (e) { out(e); }
}

async function upload() {
  try {
    saveAuth();
    const f = document.getElementById('file').files[0];
    if (!f) return out("Choose a file first.");
    const fd = new FormData();
    fd.append('title', document.getElementById('titleAud').value);
    const email = document.getElementById('emailAud').value.trim();
    if (email) fd.append('email_to', email);
    const lang = document.getElementById('lang').value.trim();
    if (lang) fd.append('language', lang);
    const hints = document.getElementById('hints').value.trim();
    if (hints) fd.append('hints', hints);
    fd.append('file', f, f.name);

    const r = await fetch('/meetings/upload', {
      method: 'POST',
      headers: authHeaders(),  // do NOT set Content-Type when using FormData
      body: fd
    });
    const j = await r.json();
    out(j);
  } catch (e) { out(e); }
}
</script>
</body></html>
    """
