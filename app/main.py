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
    </style>
    <script>
      function handleFormSubmit(form, endpoint) {{
        form.addEventListener('submit', async (e) => {{
          e.preventDefault();
          const formData = new FormData(form);
          
          try {{
            const response = await fetch(endpoint, {{
              method: 'POST',
              body: formData,
              credentials: 'include'
            }});
            
            const result = await response.json();
            if (result.id) {{
              window.location.href = `/progress?id=${{result.id}}`;
            }} else {{
              alert('Success! Meeting ID: ' + JSON.stringify(result));
            }}
          }} catch (error) {{
            alert('Error: ' + error.message);
          }}
        }});
      }}
      
      window.addEventListener('DOMContentLoaded', () => {{
        const textForm = document.getElementById('textForm');
        const uploadForm = document.getElementById('uploadForm');
        
        if (textForm) handleFormSubmit(textForm, '/meetings/from-text');
        if (uploadForm) handleFormSubmit(uploadForm, '/meetings/upload');
      }});
    </script>
    </head><body>
    <h1>AI Meeting Notes – Test</h1>

    {auth_section}

    <div class="box">
      <h2>From Transcript (No Audio)</h2>
      <p class="muted">This endpoint is protected; after login your browser will include the cookie automatically.</p>
      <form id="textForm">
        <label>Title</label>
        <input name="title" required />
        <label>Transcript</label>
        <textarea name="transcript" rows="10" placeholder="Paste transcript here…" required></textarea>
        <label>Email results to (optional)</label>
        <input type="email" name="email_to" />
        <br/>
        <button type="submit">Summarize & Show Progress</button>
      </form>
    </div>

    <div class="box">
      <h2>Upload Meeting (Audio/Video)</h2>
      <p class="muted">On Railway we recommend cloud ASR (AssemblyAI); no ffmpeg needed in the container.</p>
      <form id="uploadForm" enctype="multipart/form-data">
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
        <br/><br/>
        <button type="submit">Upload & Show Progress</button>
      </form>
    </div>

    <p class="muted">Tip: If you're testing on localhost (http), set <code>COOKIE_SECURE=0</code>. On Railway (https), keep <code>COOKIE_SECURE=1</code>.</p>
    </body></html>
    """

@app.get("/progress", response_class=HTMLResponse)
def progress_page():
    """Progress tracking and results page"""
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Meeting Progress</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    body {
      font-family: system-ui, -apple-system, sans-serif;
      margin: 0;
      padding: 20px;
      max-width: 900px;
      margin: 0 auto;
      background: #f5f5f5;
    }
    .container {
      background: white;
      border-radius: 12px;
      padding: 24px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    h1 {
      margin: 0 0 8px 0;
      font-size: 24px;
    }
    .status-badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 500;
      margin-bottom: 20px;
    }
    .status-processing { background: #fef3c7; color: #92400e; }
    .status-delivered { background: #d1fae5; color: #065f46; }
    .status-failed { background: #fee2e2; color: #991b1b; }
    .status-queued { background: #e0e7ff; color: #3730a3; }
    
    .progress-section {
      margin: 20px 0;
    }
    .progress-bar-container {
      width: 100%;
      height: 24px;
      background: #e5e7eb;
      border-radius: 12px;
      overflow: hidden;
      margin: 12px 0;
    }
    .progress-bar {
      height: 100%;
      background: linear-gradient(90deg, #3b82f6, #2563eb);
      transition: width 0.3s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: 12px;
      font-weight: 600;
    }
    .step-text {
      color: #6b7280;
      font-size: 14px;
      margin-top: 8px;
    }
    
    .results-section {
      margin-top: 32px;
      display: none;
    }
    .results-section.visible {
      display: block;
    }
    
    .section-title {
      font-size: 18px;
      font-weight: 600;
      margin: 24px 0 12px 0;
      color: #111827;
    }
    
    .summary-box {
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 16px;
      margin: 12px 0;
      white-space: pre-wrap;
      line-height: 1.6;
    }
    
    .decisions-list {
      list-style: none;
      padding: 0;
    }
    .decisions-list li {
      padding: 10px 16px;
      background: #fef3c7;
      border-left: 3px solid #f59e0b;
      margin: 8px 0;
      border-radius: 4px;
    }
    
    .action-items-table {
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0;
    }
    .action-items-table th {
      background: #f3f4f6;
      padding: 10px;
      text-align: left;
      font-weight: 600;
      font-size: 13px;
      color: #374151;
    }
    .action-items-table td {
      padding: 10px;
      border-bottom: 1px solid #e5e7eb;
    }
    .action-items-table tr:last-child td {
      border-bottom: none;
    }
    .priority-high { 
      display: inline-block;
      padding: 2px 8px;
      background: #fee2e2;
      color: #991b1b;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }
    .priority-medium { 
      display: inline-block;
      padding: 2px 8px;
      background: #fef3c7;
      color: #92400e;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }
    .priority-low { 
      display: inline-block;
      padding: 2px 8px;
      background: #e0e7ff;
      color: #3730a3;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }
    
    .email-form {
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 20px;
      margin: 20px 0;
    }
    .form-group {
      margin-bottom: 16px;
    }
    .form-group label {
      display: block;
      margin-bottom: 6px;
      font-weight: 500;
      font-size: 14px;
      color: #374151;
    }
    .form-group input {
      width: 100%;
      padding: 10px;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      font-size: 14px;
      box-sizing: border-box;
    }
    .form-group input:focus {
      outline: none;
      border-color: #3b82f6;
      box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }
    
    .btn {
      padding: 10px 20px;
      border: none;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
    }
    .btn-primary {
      background: #3b82f6;
      color: white;
    }
    .btn-primary:hover {
      background: #2563eb;
    }
    .btn-secondary {
      background: #e5e7eb;
      color: #374151;
      margin-left: 8px;
    }
    .btn-secondary:hover {
      background: #d1d5db;
    }
    
    .download-links {
      margin: 16px 0;
    }
    .download-links a {
      display: inline-block;
      padding: 8px 16px;
      background: #f3f4f6;
      color: #374151;
      text-decoration: none;
      border-radius: 6px;
      margin-right: 8px;
      font-size: 14px;
      transition: background 0.2s;
    }
    .download-links a:hover {
      background: #e5e7eb;
    }
    
    .alert {
      padding: 12px 16px;
      border-radius: 6px;
      margin: 12px 0;
      font-size: 14px;
    }
    .alert-success {
      background: #d1fae5;
      color: #065f46;
      border: 1px solid #6ee7b7;
    }
    .alert-error {
      background: #fee2e2;
      color: #991b1b;
      border: 1px solid #fca5a5;
    }
    
    .spinner {
      display: inline-block;
      width: 14px;
      height: 14px;
      border: 2px solid #f3f4f6;
      border-top: 2px solid #3b82f6;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin-right: 8px;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1 id="meetingTitle">Loading...</h1>
    <span id="statusBadge" class="status-badge">Loading</span>
    
    <div class="progress-section" id="progressSection">
      <div class="progress-bar-container">
        <div class="progress-bar" id="progressBar">0%</div>
      </div>
      <div class="step-text" id="stepText">Initializing...</div>
    </div>
    
    <div class="results-section" id="resultsSection">
      <div class="section-title">Executive Summary</div>
      <div class="summary-box" id="executiveSummary"></div>
      
      <div class="section-title">Key Decisions</div>
      <ul class="decisions-list" id="decisionsList"></ul>
      
      <div class="section-title">Action Items</div>
      <table class="action-items-table">
        <thead>
          <tr>
            <th>Owner</th>
            <th>Task</th>
            <th>Due Date</th>
            <th>Priority</th>
          </tr>
        </thead>
        <tbody id="actionItemsBody"></tbody>
      </table>
      
      <div class="section-title">Downloads</div>
      <div class="download-links">
        <a id="downloadTranscript" href="#" style="display:none">📄 Download Transcript</a>
        <a id="downloadSummary" href="#" style="display:none">📋 Download Summary</a>
      </div>
      
      <div class="section-title">Send Summary via Email</div>
      <div class="email-form">
        <div id="emailAlert"></div>
        <div class="form-group">
          <label>Email Address</label>
          <input type="email" id="emailInput" placeholder="recipient@example.com">
        </div>
        <button class="btn btn-primary" onclick="sendEmail()">
          <span id="sendBtnText">Send Email</span>
        </button>
        <button class="btn btn-secondary" onclick="window.location.href='/upload-test'">
          Back to Upload
        </button>
      </div>
    </div>
  </div>

  <script>
    const meetingId = new URLSearchParams(window.location.search).get('id');
    let pollInterval = null;
    
    async function fetchMeetingStatus() {
      try {
        const response = await fetch(`/meetings/${meetingId}`, {
          credentials: 'include'
        });
        if (!response.ok) throw new Error('Failed to fetch meeting');
        const meeting = await response.json();
        updateUI(meeting);
        
        // Stop polling if complete or failed
        if (meeting.status === 'delivered' || meeting.status === 'failed') {
          if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
          }
          
          // Fetch and display results
          if (meeting.status === 'delivered' && meeting.summary_path) {
            await fetchResults(meeting);
          }
        }
      } catch (error) {
        console.error('Error fetching meeting status:', error);
      }
    }
    
    function updateUI(meeting) {
      // Update title and status
      document.getElementById('meetingTitle').textContent = meeting.title;
      
      const statusBadge = document.getElementById('statusBadge');
      statusBadge.textContent = meeting.status.toUpperCase();
      statusBadge.className = `status-badge status-${meeting.status}`;
      
      // Update progress
      const progress = meeting.progress || 0;
      const progressBar = document.getElementById('progressBar');
      progressBar.style.width = `${progress}%`;
      progressBar.textContent = `${progress}%`;
      
      // Update step text
      const stepText = document.getElementById('stepText');
      if (meeting.step) {
        stepText.innerHTML = `<span class="spinner"></span>${meeting.step}`;
      }
      
      // Show/hide progress section
      const progressSection = document.getElementById('progressSection');
      if (meeting.status === 'delivered' || meeting.status === 'failed') {
        progressSection.style.display = 'none';
      }
      
      // Setup download links
      if (meeting.transcript_path) {
        const link = document.getElementById('downloadTranscript');
        link.href = `/meetings/${meetingId}/download/transcript`;
        link.style.display = 'inline-block';
      }
      if (meeting.summary_path) {
        const link = document.getElementById('downloadSummary');
        link.href = `/meetings/${meetingId}/download/summary`;
        link.style.display = 'inline-block';
      }
    }
    
    async function fetchResults(meeting) {
      try {
        const response = await fetch(`/meetings/${meetingId}/download/summary`, {
          credentials: 'include'
        });
        if (!response.ok) return;
        
        const summary = await response.json();
        displayResults(summary);
        
        // Pre-fill email if available
        if (meeting.email_to) {
          document.getElementById('emailInput').value = meeting.email_to;
        }
      } catch (error) {
        console.error('Error fetching results:', error);
      }
    }
    
    function displayResults(summary) {
      // Show results section
      document.getElementById('resultsSection').classList.add('visible');
      
      // Executive summary
      const execSummary = summary.executive_summary || 'No summary available';
      document.getElementById('executiveSummary').textContent = execSummary;
      
      // Key decisions
      const decisionsList = document.getElementById('decisionsList');
      const decisions = summary.key_decisions || [];
      if (decisions.length === 0) {
        decisionsList.innerHTML = '<li>No key decisions recorded</li>';
      } else {
        decisionsList.innerHTML = decisions.map(d => `<li>${d}</li>`).join('');
      }
      
      // Action items
      const actionItemsBody = document.getElementById('actionItemsBody');
      const actionItems = summary.action_items || [];
      if (actionItems.length === 0) {
        actionItemsBody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#6b7280">No action items</td></tr>';
      } else {
        actionItemsBody.innerHTML = actionItems.map(item => {
          const priority = item.priority || 'Medium';
          const priorityClass = `priority-${priority.toLowerCase()}`;
          return `
            <tr>
              <td>${item.owner || '-'}</td>
              <td>${item.task || '-'}</td>
              <td>${item.due_date || '-'}</td>
              <td><span class="${priorityClass}">${priority}</span></td>
            </tr>
          `;
        }).join('');
      }
    }
    
    async function sendEmail() {
      const email = document.getElementById('emailInput').value.trim();
      if (!email) {
        showAlert('Please enter an email address', 'error');
        return;
      }
      
      const btn = document.getElementById('sendBtnText');
      btn.innerHTML = '<span class="spinner"></span>Sending...';
      
      try {
        const response = await fetch(`/meetings/${meetingId}/send-email`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ email_to: email })
        });
        
        if (!response.ok) throw new Error('Failed to send email');
        
        showAlert('Email sent successfully!', 'success');
      } catch (error) {
        showAlert('Failed to send email. Please try again.', 'error');
      } finally {
        btn.textContent = 'Send Email';
      }
    }
    
    function showAlert(message, type) {
      const alertDiv = document.getElementById('emailAlert');
      alertDiv.className = `alert alert-${type}`;
      alertDiv.textContent = message;
      setTimeout(() => {
        alertDiv.textContent = '';
        alertDiv.className = '';
      }, 5000);
    }
    
    // Initialize
    if (meetingId) {
      fetchMeetingStatus();
      // Poll every 2 seconds while processing
      pollInterval = setInterval(fetchMeetingStatus, 2000);
    } else {
      document.body.innerHTML = '<div class="container"><h1>Error: No meeting ID provided</h1></div>';
    }
  </script>
</body>
</html>
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
  <title>AI Meeting Notes – Browser Test</title>
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
  <h1>AI Meeting Notes – Browser Test</h1>

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