from fastapi import FastAPI, Request
from .security import COOKIE_NAME
from fastapi.middleware.cors import CORSMiddleware
from .db import init_db
import os
from fastapi.responses import HTMLResponse
from .services.branding import render_meeting_notes_email_html
from pathlib import Path
from .routers import meetings, health, auth, license

os.environ["PATH"] = r"C:\Tools\ffmpeg\bin;" + os.environ["PATH"]

app = FastAPI(title="Clipnote")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# Include license router
app.include_router(license.router)

@app.get("/activate", response_class=HTMLResponse)
def activate_page():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Activate License - Clipnote</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .container {
      background: white;
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
      max-width: 500px;
      width: 100%;
      padding: 40px;
    }
    h1 {
      font-size: 28px;
      margin-bottom: 8px;
      color: #1a202c;
    }
    .subtitle {
      color: #718096;
      margin-bottom: 32px;
      font-size: 15px;
    }
    .form-group {
      margin-bottom: 24px;
    }
    label {
      display: block;
      font-weight: 600;
      margin-bottom: 8px;
      color: #2d3748;
      font-size: 14px;
    }
    input {
      width: 100%;
      padding: 12px 16px;
      border: 2px solid #e2e8f0;
      border-radius: 8px;
      font-size: 16px;
      transition: all 0.2s;
      font-family: "Monaco", "Courier New", monospace;
      letter-spacing: 1px;
    }
    input:focus {
      outline: none;
      border-color: #667eea;
      box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    .btn {
      width: 100%;
      padding: 14px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      border: none;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.3s;
    }
    .btn:hover {
      transform: translateY(-2px);
      box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
    }
    .btn:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }
    .alert {
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 20px;
      font-size: 14px;
    }
    .alert-success {
      background: #c6f6d5;
      color: #22543d;
      border: 1px solid #9ae6b4;
    }
    .alert-error {
      background: #fed7d7;
      color: #742a2a;
      border: 1px solid #fc8181;
    }
    .help-text {
      margin-top: 12px;
      font-size: 13px;
      color: #718096;
    }
    .help-text a {
      color: #667eea;
      text-decoration: none;
    }
    .help-text a:hover {
      text-decoration: underline;
    }
    .format-hint {
      font-size: 12px;
      color: #a0aec0;
      margin-top: 6px;
      font-family: "Monaco", "Courier New", monospace;
    }
    .spinner {
      display: inline-block;
      width: 14px;
      height: 14px;
      border: 2px solid #ffffff;
      border-top: 2px solid transparent;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
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
    <h1>🎉 Welcome!</h1>
    <p class="subtitle">Activate your Clipnote license to get started</p>
    
    <div id="alertBox"></div>
    
    <form id="activationForm">
      <div class="form-group">
        <label for="licenseKey">License Key</label>
        <input 
          type="text" 
          id="licenseKey" 
          placeholder="STA-XXXX-XXXX-XXXX-XXXX"
          required
          autocomplete="off"
          spellcheck="false"
        >
        <div class="format-hint">Format: XXX-XXXX-XXXX-XXXX-XXXX</div>
      </div>
      
      <button type="submit" class="btn" id="submitBtn">
        <span id="btnText">Activate License</span>
      </button>
      
      <p class="help-text">
        Don't have a license? <a href="https://gumroad.com/your-product" target="_blank">Purchase one here</a><br>
        Need help? Contact <a href="mailto:support@yourdomain.com">support@yourdomain.com</a>
      </p>
    </form>
  </div>

  <script>
    const form = document.getElementById('activationForm');
    const input = document.getElementById('licenseKey');
    const submitBtn = document.getElementById('submitBtn');
    const btnText = document.getElementById('btnText');
    const alertBox = document.getElementById('alertBox');

    input.addEventListener('input', (e) => {
      let value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
      
      // Format: XXX-XXXX-XXXX-XXXX-XXXX (3 chars, then 4 groups of 4)
      let formatted = '';
      if (value.length > 0) {
        formatted = value.substring(0, 3); // First 3 chars
        if (value.length > 3) {
          formatted += '-' + value.substring(3, 7); // Next 4
        }
        if (value.length > 7) {
          formatted += '-' + value.substring(7, 11); // Next 4
        }
        if (value.length > 11) {
          formatted += '-' + value.substring(11, 15); // Next 4
        }
        if (value.length > 15) {
          formatted += '-' + value.substring(15, 19); // Last 4
        }
      }
      
      e.target.value = formatted;
    });

    function showAlert(message, type) {
      alertBox.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
      setTimeout(() => {
        if (type !== 'success') {
          alertBox.innerHTML = '';
        }
      }, 5000);
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const licenseKey = input.value.trim();
      
      if (!licenseKey) {
        showAlert('Please enter your license key', 'error');
        return;
      }

      submitBtn.disabled = true;
      btnText.innerHTML = '<span class="spinner"></span>Activating...';

      try {
        const response = await fetch('/license/activate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ license_key: licenseKey })
        });

        const data = await response.json();

        if (response.ok) {
          showAlert('✅ License activated successfully! Redirecting...', 'success');
          setTimeout(() => {
            window.location.href = '/upload-test';
          }, 2000);
        } else {
          showAlert(data.detail || 'Invalid license key', 'error');
          submitBtn.disabled = false;
          btnText.textContent = 'Activate License';
        }
      } catch (error) {
        showAlert('Connection error. Please try again.', 'error');
        submitBtn.disabled = false;
        btnText.textContent = 'Activate License';
      }
    });
  </script>
</body>
</html>
"""

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
    <title>Clipnote – Test</title>
    <style>
      body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:40px;max-width:960px}}
      input,textarea{{width:100%;padding:8px}} label{{display:block;margin:10px 0 4px}}
      .row{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
      .box{{padding:16px;border:1px solid #ddd;border-radius:10px;margin-bottom:28px}}
      button{{padding:10px 16px;border-radius:10px;background:#111;color:#fff;border:none;cursor:pointer}}
      small{{color:#555}}
      .muted{{color:#555}}
      
      /* License Widget Styles */
      .license-widget {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      }}
      .license-loading {{ text-align: center; opacity: 0.8; }}
      .license-content {{ display: grid; grid-template-columns: 1fr auto; gap: 20px; align-items: center; }}
      .license-info h3 {{ margin: 0 0 8px 0; font-size: 18px; font-weight: 600; }}
      .license-tier {{
        display: inline-block;
        background: rgba(255,255,255,0.2);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 12px;
      }}
      .license-stats {{ display: flex; gap: 24px; font-size: 14px; opacity: 0.95; }}
      .license-stat {{ display: flex; flex-direction: column; }}
      .stat-label {{ opacity: 0.8; font-size: 12px; margin-bottom: 4px; }}
      .stat-value {{ font-size: 18px; font-weight: 700; }}
      .license-actions {{ display: flex; flex-direction: column; gap: 8px; }}
      .license-btn {{
        background: rgba(255,255,255,0.2);
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        font-size: 13px;
        cursor: pointer;
        transition: all 0.2s;
        white-space: nowrap;
      }}
      .license-btn:hover {{ background: rgba(255,255,255,0.3); }}
      .quota-bar {{
        background: rgba(255,255,255,0.2);
        border-radius: 10px;
        height: 8px;
        overflow: hidden;
        margin-top: 8px;
      }}
      .quota-fill {{
        background: rgba(255,255,255,0.9);
        height: 100%;
        transition: width 0.3s;
      }}
      .quota-warning {{ background: #fbbf24; }}
      .quota-danger {{ background: #ef4444; }}
      .license-error {{
        background: #fee2e2;
        color: #991b1b;
        padding: 16px;
        border-radius: 8px;
        border: 1px solid #fca5a5;
      }}
    </style>
    <script>
      async function loadLicenseInfo() {{
        const widget = document.getElementById('licenseWidget');
        
        try {{
          const response = await fetch('/license/info', {{
            credentials: 'include'
          }});
          
          const data = await response.json();
          
          if (!data.valid) {{
            widget.innerHTML = `
              <div class="license-error">
                <strong>⚠️ No Active License</strong><br>
                ${{data.error || 'Please activate your license to continue.'}}<br>
                <a href="/activate" style="color: #991b1b; text-decoration: underline; margin-top: 8px; display: inline-block;">
                  Activate License →
                </a>
              </div>
            `;
            return;
          }}
          
          const quotaPercent = data.meetings_limit > 0 
            ? (data.meetings_used / data.meetings_limit * 100) 
            : 0;
          
          let quotaClass = '';
          if (quotaPercent >= 90) quotaClass = 'quota-danger';
          else if (quotaPercent >= 75) quotaClass = 'quota-warning';
          
          const remaining = data.meetings_limit - data.meetings_used;
          
          widget.innerHTML = `
            <div class="license-content">
              <div class="license-info">
                <h3>👋 ${{data.email}}</h3>
                <span class="license-tier">${{data.tier_name}} Plan</span>
                
                <div class="license-stats">
                  <div class="license-stat">
                    <span class="stat-label">Meetings This Month</span>
                    <span class="stat-value">${{data.meetings_used}} / ${{data.meetings_limit === 999999 ? '∞' : data.meetings_limit}}</span>
                  </div>
                  <div class="license-stat">
                    <span class="stat-label">Max File Size</span>
                    <span class="stat-value">${{data.max_file_size_mb}}MB</span>
                  </div>
                  ${{data.meetings_limit < 999999 ? `
                    <div class="license-stat">
                      <span class="stat-label">Remaining</span>
                      <span class="stat-value">${{remaining}}</span>
                    </div>
                  ` : ''}}
                </div>
                
                ${{data.meetings_limit < 999999 ? `
                  <div class="quota-bar">
                    <div class="quota-fill ${{quotaClass}}" style="width: ${{Math.min(quotaPercent, 100)}}%"></div>
                  </div>
                ` : ''}}
              </div>
              
              <div class="license-actions">
                <button class="license-btn" onclick="copyLicenseKey()">📋 Copy Key</button>
                <button class="license-btn" onclick="window.location.href='https://gumroad.com/your-product'">
                  ⬆️ Upgrade
                </button>
              </div>
            </div>
          `;
          
          window.currentLicenseKey = data.license_key;
          
        }} catch (error) {{
          console.error('Failed to load license info:', error);
          widget.innerHTML = `
            <div class="license-error">
              Failed to load license information. Please refresh the page.
            </div>
          `;
        }}
      }}

      function copyLicenseKey() {{
        if (window.currentLicenseKey) {{
          navigator.clipboard.writeText(window.currentLicenseKey);
          alert('License key copied to clipboard!');
        }}
      }}

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
        loadLicenseInfo();
        const textForm = document.getElementById('textForm');
        const uploadForm = document.getElementById('uploadForm');
        
        if (textForm) handleFormSubmit(textForm, '/meetings/from-text');
        if (uploadForm) handleFormSubmit(uploadForm, '/meetings/upload');
      }});
    </script>
    </head><body>
    <div class="titlebar">
      <h1>Clipnote – Test</h1>
      <button><a class="btn btn-secondary" href="/meetings" id="meetingsBtn">Meetings</a></button>
    </div>

    {auth_section}

    <!-- License Widget -->
    <div class="license-widget" id="licenseWidget">
      <div class="license-loading">Loading license info...</div>
    </div>

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
    
    .titlebar{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      margin-bottom:16px;
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
        const response = await fetch(`/meetings/${meetingId}/summary`, {
          credentials: 'include'
        });
        
        console.log('Response status:', response.status);
        console.log('Response headers:', response.headers.get('content-type'));
        
        if (!response.ok) {
          console.error('Response not OK:', response.status);
          return;
        }
        
        const summary = await response.json();
        displayResults(summary);
        
        // Pre-fill email if available
        if (meeting.email_to) {
          document.getElementById('emailInput').value = meeting.email_to;
        }
      } catch (error) {
        console.error('Error fetching results:', error);
        console.error('Error details:', error.message);
        // Show error in UI
        document.getElementById('resultsSection').classList.add('visible');
        document.getElementById('executiveSummary').textContent = 
          'Error loading summary. Check console for details. Error: ' + error.message;
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

@app.get("/", response_class=HTMLResponse)
def index():
    """Homepage - Landing page"""
    # Get the directory where this file is located (app/)
    current_dir = Path(__file__).parent
    html_path = current_dir / "templates" / "index.html"
    
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    else:
        # Fallback with proper error message
        return f"""
        <!doctype html>
        <html>
        <head><meta charset="utf-8"><title>Error</title></head>
        <body>
          <h1>Homepage not found</h1>
          <p>Looking for: {html_path}</p>
          <p>File exists: {html_path.exists()}</p>
          <p><a href="/upload-test">Go to Upload Test</a></p>
        </body>
        </html>
        """

@app.get("/meetings", response_class=HTMLResponse)
def meetings_list_page(request: Request):
    """Meeting history list page"""
    logged_in = COOKIE_NAME in request.cookies
    if not logged_in:
        return """
        <!doctype html>
        <meta charset="utf-8">
        <meta http-equiv="refresh" content="0;url=/login">
        <title>Login Required</title>
        <p>Redirecting to <a href="/login">login page</a>...</p>
        """
    
    # Inline the meetings list HTML from artifact
    return open("meetings_list.html").read() if Path("meetings_list.html").exists() else """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Meeting History</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
    .container { max-width: 1200px; margin: 0 auto; }
    .header { background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; }
    h1 { margin: 0; font-size: 28px; }
    .filters { display: flex; gap: 12px; margin-bottom: 20px; }
    .filter-btn { padding: 8px 16px; border: 1px solid #d1d5db; background: white; border-radius: 6px; cursor: pointer; transition: all 0.2s; font-size: 14px; }
    .filter-btn:hover { background: #f3f4f6; }
    .filter-btn.active { background: #3b82f6; color: white; border-color: #3b82f6; }
    .meetings-grid { display: grid; gap: 16px; }
    .meeting-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); cursor: pointer; transition: all 0.2s; display: grid; grid-template-columns: 1fr auto; gap: 16px; }
    .meeting-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.15); transform: translateY(-2px); }
    .meeting-info h3 { margin: 0 0 8px 0; font-size: 18px; color: #111827; }
    .meeting-meta { display: flex; gap: 16px; color: #6b7280; font-size: 14px; }
    .meeting-actions { display: flex; gap: 8px; align-items: center; }
    .status-badge { padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
    .status-processing { background: #fef3c7; color: #92400e; }
    .status-delivered { background: #d1fae5; color: #065f46; }
    .status-failed { background: #fee2e2; color: #991b1b; }
    .status-queued { background: #e0e7ff; color: #3730a3; }
    .btn { padding: 8px 16px; border: none; border-radius: 6px; font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.2s; }
    .btn-primary { background: #3b82f6; color: white; }
    .btn-primary:hover { background: #2563eb; }
    .btn-danger { background: #ef4444; color: white; }
    .btn-danger:hover { background: #dc2626; }
    .btn-secondary { background: #e5e7eb; color: #374151; }
    .btn-secondary:hover { background: #d1d5db; }
    .btn-small { padding: 6px 12px; font-size: 13px; }
    .empty-state { background: white; border-radius: 12px; padding: 60px 20px; text-align: center; color: #6b7280; }
    .empty-state h2 { margin: 0 0 8px 0; color: #374151; }
    .loading { text-align: center; padding: 40px; color: #6b7280; }
    .error-message { color: #ef4444; font-size: 13px; margin-top: 4px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Meeting History</h1>
      <button class="btn btn-primary" onclick="window.location.href='/upload-test'">+ New Meeting</button>
    </div>
    <div class="filters">
      <button class="filter-btn active" data-filter="all">All</button>
      <button class="filter-btn" data-filter="delivered">Delivered</button>
      <button class="filter-btn" data-filter="processing">Processing</button>
      <button class="filter-btn" data-filter="failed">Failed</button>
      <button class="filter-btn" data-filter="queued">Queued</button>
    </div>
    <div id="meetingsContainer"><div class="loading">Loading meetings...</div></div>
  </div>
  <script>
    let allMeetings = [];
    let currentFilter = 'all';
    async function fetchMeetings() {
      try {
        const response = await fetch('/meetings/list', { credentials: 'include' });
        if (!response.ok) throw new Error('Failed to fetch meetings');
        allMeetings = await response.json();
        renderMeetings();
      } catch (error) {
        console.error('Error:', error);
        document.getElementById('meetingsContainer').innerHTML = '<div class="empty-state"><h2>Error loading meetings</h2><p>' + error.message + '</p></div>';
      }
    }
    function renderMeetings() {
      const container = document.getElementById('meetingsContainer');
      let filtered = currentFilter === 'all' ? allMeetings : allMeetings.filter(m => m.status === currentFilter);
      
      if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-state"><h2>No meetings found</h2><p>Upload your first meeting to get started</p></div>';
        return;
      }
      
      const grid = document.createElement('div');
      grid.className = 'meetings-grid';
      
      filtered.forEach(meeting => {
        const card = document.createElement('div');
        card.className = 'meeting-card';
        card.onclick = () => viewMeeting(meeting.id);
        
        const info = document.createElement('div');
        info.className = 'meeting-info';
        
        const title = document.createElement('h3');
        title.textContent = meeting.title;
        info.appendChild(title);
        
        const meta = document.createElement('div');
        meta.className = 'meeting-meta';
        meta.innerHTML = '<span>Created: ' + new Date(meeting.created_at).toLocaleString() + '</span>';
        if (meeting.email_to) {
          const email = document.createElement('span');
          email.textContent = '📧 ' + meeting.email_to;
          meta.appendChild(email);
        }
        info.appendChild(meta);
        
        if (meeting.status === 'failed' && meeting.step) {
          const error = document.createElement('div');
          error.className = 'error-message';
          error.textContent = meeting.step;
          info.appendChild(error);
        }
        
        const actions = document.createElement('div');
        actions.className = 'meeting-actions';
        actions.onclick = (e) => e.stopPropagation();
        
        const badge = document.createElement('span');
        badge.className = 'status-badge status-' + meeting.status;
        badge.textContent = meeting.status.toUpperCase();
        actions.appendChild(badge);
        
        if (meeting.status === 'failed') {
          const retry = document.createElement('button');
          retry.className = 'btn btn-secondary btn-small';
          retry.textContent = 'Retry';
          retry.onclick = () => retryMeeting(meeting.id);
          actions.appendChild(retry);
        }
        
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn btn-danger btn-small';
        deleteBtn.textContent = 'Delete';
        deleteBtn.onclick = () => deleteMeeting(meeting.id);
        actions.appendChild(deleteBtn);
        
        card.appendChild(info);
        card.appendChild(actions);
        grid.appendChild(card);
      });
      
      container.innerHTML = '';
      container.appendChild(grid);
    }
    function viewMeeting(id) { window.location.href = '/progress?id=' + id; }
    async function retryMeeting(id) {
      if (!confirm('Retry processing this meeting?')) return;
      try {
        const response = await fetch('/meetings/' + id + '/run', { method: 'POST', credentials: 'include' });
        if (!response.ok) throw new Error('Failed to retry');
        alert('Meeting queued for reprocessing');
        fetchMeetings();
      } catch (error) {
        alert('Failed to retry: ' + error.message);
      }
    }
    async function deleteMeeting(id) {
      if (!confirm('Are you sure you want to delete this meeting? This cannot be undone.')) return;
      try {
        const response = await fetch('/meetings/' + id, { method: 'DELETE', credentials: 'include' });
        if (!response.ok) throw new Error('Failed to delete');
        allMeetings = allMeetings.filter(m => m.id !== id);
        renderMeetings();
      } catch (error) {
        alert('Failed to delete: ' + error.message);
      }
    }
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        renderMeetings();
      });
    });
    fetchMeetings();
    setInterval(fetchMeetings, 5000);
  </script>
</body>
</html>
    """
    
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
  <title>Clipnote – Browser Test</title>
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
  <h1>Clipnote – Browser Test</h1>

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