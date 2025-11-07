from fastapi import FastAPI, Request, HTTPException
from .security import COOKIE_NAME
from fastapi.middleware.cors import CORSMiddleware
from app.db import init_db, DATA_DIR, get_session
from fastapi.responses import JSONResponse
import stripe
import os
from fastapi.responses import HTMLResponse
from .services.branding import render_meeting_notes_email_html
from pathlib import Path
from dotenv import load_dotenv
from sqlmodel import select, Session

from app.models import Meeting
import warnings
warnings.filterwarnings("ignore", message="Field .* has conflict with protected namespace 'model_'")

from fastapi import Depends
from sqlalchemy.orm import Session

load_dotenv()  # ✅ This loads your .env file

os.environ["PATH"] = r"C:\Tools\ffmpeg\bin;" + os.environ["PATH"]

app = FastAPI(title="Clipnote")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://4dgaming.games",
        "https://ai-meeting-notes-production-81d7.up.railway.app",
        "http://localhost:8080",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Service pricing (in cents)
SERVICE_PRICES = {
    "chatbot": {"price": 15000, "name": "AI Chatbot Development"},
    "mobile": {"price": 50000, "name": "Mobile App Development"},
    "game": {"price": 20000, "name": "Game Development & Reskinning"},
    "web3": {"price": 30000, "name": "Web3 & Blockchain Development"},
    "scraping": {"price": 5000, "name": "Web Scraping & Lead Gen"},
    "pdf": {"price": 20000, "name": "PDF Generation"},
    "nft": {"price": 25000, "name": "NFT & Metaverse Assets"},
    "publishing": {"price": 10000, "name": "App Store Publishing"},
    "transcription": {"price": 1000, "name": "AI Transcription Service"},
    "trading": {"price": 50000, "name": "Trading Bot Development"}
}

# ✅ Run path verification on startup
@app.on_event("startup")
async def startup_event():
    """Run verification on startup to fix any broken file paths"""
    print("🚀 Application starting up...")
    try:
        verify_and_fix_meeting_paths()
    except Exception as e:
        print(f"⚠️ Warning: Path verification failed: {e}")
        print("Continuing with startup anyway...")
    print("✅ Startup complete\n")

from .routers import meetings, health, auth, license
from app.routers.storage_b2 import router as storage_router
from app.routers import iap
from app.app_uploads import router as uploads_router
from app.meeting_api import router as meeting_router
from app.routers import admin
# Include license router
app.include_router(license.router)
app.include_router(storage_router)
app.include_router(uploads_router)
app.include_router(meeting_router)
app.include_router(iap.router)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(meetings.router)
app.include_router(admin.router)

@app.get("/healthz")
def healthz():
    return {"ok": True}
  
@app.get("/")
async def root():
    return {"message": "4D Gaming Stripe Backend", "status": "active"}

# ==================== 4D GAMING STRIPE ENDPOINTS ====================

@app.get("/config")
async def get_stripe_config():
    """Return Stripe publishable key for 4D Gaming frontend"""
    publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY")
    if not publishable_key:
        raise HTTPException(status_code=500, detail="Stripe key not configured")
    return {"publishableKey": publishable_key}

@app.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    """Create Stripe checkout session for 4D Gaming services"""
    try:
        data = await request.json()
        service = data.get("service")
        
        if service not in SERVICE_PRICES:
            raise HTTPException(status_code=400, detail="Invalid service")
        
        service_data = SERVICE_PRICES[service]
        origin = request.headers.get("origin", "https://4dgaming.games")
        
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": service_data["name"],
                        "description": f"Professional {service_data['name']} service by 4D Gaming",
                        "metadata": {
                            "business": "4D Gaming",
                            "category": service
                        }
                    },
                    "unit_amount": service_data["price"],
                },
                "quantity": 1,
            }],
            mode="payment",
            payment_intent_data={
                "statement_descriptor": "4D GAMING",
                "statement_descriptor_suffix": "DEV",
            },
            success_url=f"{origin}/success.html?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/#services",
            metadata={
                "business": "4D Gaming",
                "service_type": service
            }
        )
        
        return {"id": session.id}
        
    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/checkout-session")
async def get_checkout_session_details(sessionId: str):
    """Retrieve checkout session details for success page"""
    try:
        session = stripe.checkout.Session.retrieve(sessionId)
        return session
    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def stripe_webhook_handler(request: Request):
    """Handle Stripe webhooks for payment confirmations"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle the checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        print(f"💰 4D Gaming payment successful! Session: {session['id']}")
        # TODO: Send confirmation email to customer
        # TODO: Send notification to you
    
    return {"received": True}
  
def verify_and_fix_meeting_paths():
    """
    On startup, check if stored file paths are valid
    If not, try to find the files in the new persistent directory
    """
    print(f"\n{'='*60}")
    print(f"🔍 STARTUP: Checking meeting file paths")
    print(f"{'='*60}")
    print(f"Data directory: {DATA_DIR}\n")
    
    with get_session() as db:
        # Get all meetings with files
        meetings = db.exec(select(Meeting)).all()
        
        if not meetings:
            print("ℹ️ No meetings found in database")
            return
        
        print(f"Found {len(meetings)} meetings to check\n")
        
        fixed_count = 0
        
        for meeting in meetings:
            print(f"Meeting {meeting.id}: {meeting.title}")
            
            # Check transcript
            if meeting.transcript_path:
                if not Path(meeting.transcript_path).exists():
                    print(f"  ⚠️ Transcript path missing: {meeting.transcript_path}")
                    
                    # Try to find it in the new persistent directory
                    transcripts_dir = DATA_DIR / "transcripts"
                    possible_files = list(transcripts_dir.glob(f"{meeting.id}_*"))
                    
                    if possible_files:
                        new_path = str(possible_files[0].resolve())
                        print(f"  ✅ Found in new location: {new_path}")
                        meeting.transcript_path = new_path
                        db.add(meeting)
                        fixed_count += 1
                    else:
                        print(f"  ❌ Could not find transcript file")
                else:
                    print(f"  ✅ Transcript: {meeting.transcript_path}")
            
            # Check summary
            if meeting.summary_path:
                if not Path(meeting.summary_path).exists():
                    print(f"  ⚠️ Summary path missing: {meeting.summary_path}")
                    
                    # Try to find it in the new persistent directory
                    summaries_dir = DATA_DIR / "summaries"
                    possible_files = list(summaries_dir.glob(f"{meeting.id}_*"))
                    
                    if possible_files:
                        new_path = str(possible_files[0].resolve())
                        print(f"  ✅ Found in new location: {new_path}")
                        meeting.summary_path = new_path
                        db.add(meeting)
                        fixed_count += 1
                    else:
                        print(f"  ❌ Could not find summary file")
                else:
                    print(f"  ✅ Summary: {meeting.summary_path}")
            
            print()
        
        if fixed_count > 0:
            print(f"\n🔧 Fixed {fixed_count} file paths")
            db.commit()
        
        print(f"{'='*60}\n")

def _page(title: str, body_html: str) -> HTMLResponse:
    html = f"""<!doctype html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} – Clipnote</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.75;color:#1a202c;background:#f7fafc;margin:0}}
  .wrap{{max-width:900px;margin:60px auto;padding:0 20px}}
  h1{{font-size:36px;margin:0 0 10px}}
  p,li{{color:#4a5568}}
  a{{color:#667eea}}
  .card{{background:#fff;border-radius:16px;box-shadow:0 4px 18px rgba(0,0,0,.06);padding:28px;margin-top:20px}}
</style></head><body>
<div class="wrap">
  <h1>{title}</h1>
  <div class="card">{body_html}</div>
</div></body></html>"""
    return HTMLResponse(html, media_type="text/html; charset=utf-8")

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

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <title>Upload Meeting - Clipnote</title>
      <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          background: #f7fafc;
          color: #1a202c;
          line-height: 1.6;
        }}
        
        /* Header */
        header {{
          background: rgba(255, 255, 255, 0.95);
          backdrop-filter: blur(10px);
          padding: 20px 0;
          box-shadow: 0 2px 10px rgba(0,0,0,0.05);
          margin-bottom: 40px;
        }}
        
        nav {{
          max-width: 1200px;
          margin: 0 auto;
          padding: 0 20px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }}
        
        .logo {{
          font-size: 24px;
          font-weight: 700;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          background-clip: text;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }}
        
        .nav-links {{
          display: flex;
          gap: 20px;
          align-items: center;
        }}
        
        .container {{
          max-width: 1200px;
          margin: 0 auto;
          padding: 0 20px 60px;
        }}
        
        .page-header {{
          text-align: center;
          margin-bottom: 48px;
        }}
        
        .page-header h1 {{
          font-size: 42px;
          margin-bottom: 12px;
          color: #1a202c;
        }}
        
        .page-header p {{
          font-size: 18px;
          color: #718096;
        }}
        
        /* Cards */
        .card {{
          background: white;
          border-radius: 16px;
          padding: 32px;
          margin-bottom: 32px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.05);
          transition: all 0.3s;
        }}
        
        .card:hover {{
          box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        }}
        
        .card-header {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
          padding-bottom: 16px;
          border-bottom: 2px solid #f7fafc;
        }}
        
        .card-header h2 {{
          font-size: 24px;
          color: #1a202c;
          margin: 0;
        }}
        
        .feature-badges {{
          display: flex;
          gap: 8px;
        }}
        
        .feature-badge {{
          display: inline-block;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          padding: 6px 14px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 600;
        }}
        
        .subtitle {{
          color: #718096;
          font-size: 15px;
          margin-bottom: 24px;
        }}
        
        /* License Widget */
        .license-widget {{
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border-radius: 16px;
          padding: 28px;
          margin-bottom: 32px;
          box-shadow: 0 8px 24px rgba(102, 126, 234, 0.25);
        }}
        
        .license-content {{
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 24px;
          align-items: center;
        }}
        
        .license-info h3 {{
          margin: 0 0 8px 0;
          font-size: 20px;
          font-weight: 600;
        }}
        
        .license-tier {{
          display: inline-block;
          background: rgba(255,255,255,0.2);
          padding: 4px 14px;
          border-radius: 20px;
          font-size: 13px;
          font-weight: 600;
          margin-bottom: 16px;
        }}
        
        .license-stats {{
          display: flex;
          gap: 28px;
          font-size: 14px;
        }}
        
        .license-stat {{
          display: flex;
          flex-direction: column;
        }}
        
        .stat-label {{
          opacity: 0.85;
          font-size: 12px;
          margin-bottom: 4px;
        }}
        
        .stat-value {{
          font-size: 22px;
          font-weight: 700;
        }}
        
        .license-actions {{
          display: flex;
          flex-direction: column;
          gap: 10px;
        }}
        
        .license-btn {{
          background: rgba(255,255,255,0.2);
          color: white;
          border: none;
          padding: 10px 18px;
          border-radius: 8px;
          font-size: 14px;
          cursor: pointer;
          transition: all 0.2s;
          white-space: nowrap;
          font-weight: 500;
        }}
        
        .license-btn:hover {{
          background: rgba(255,255,255,0.3);
          transform: translateY(-1px);
        }}
        
        .quota-bar {{
          background: rgba(255,255,255,0.2);
          border-radius: 10px;
          height: 8px;
          overflow: hidden;
          margin-top: 12px;
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
          padding: 20px;
          border-radius: 12px;
          border: 1px solid #fca5a5;
        }}
        
        /* Forms */
        .form-group {{
          margin-bottom: 20px;
        }}
        
        .form-row {{
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
        }}
        
        label {{
          display: block;
          font-weight: 600;
          margin-bottom: 8px;
          color: #2d3748;
          font-size: 14px;
        }}
        
        input[type="text"],
        input[type="email"],
        textarea,
        select {{
          width: 100%;
          padding: 12px 16px;
          border: 2px solid #e2e8f0;
          border-radius: 10px;
          font-size: 15px;
          transition: all 0.2s;
          font-family: inherit;
        }}
        
        input[type="file"] {{
          width: 100%;
          padding: 12px;
          border: 2px dashed #e2e8f0;
          border-radius: 10px;
          cursor: pointer;
          transition: all 0.2s;
        }}
        
        input:focus,
        textarea:focus,
        select:focus {{
          outline: none;
          border-color: #667eea;
          box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}
        
        input[type="file"]:hover {{
          border-color: #667eea;
          background: #f7fafc;
        }}
        
        textarea {{
          resize: vertical;
          min-height: 120px;
        }}
        
        .help-text {{
          font-size: 13px;
          color: #718096;
          margin-top: 6px;
        }}
        
        /* Buttons */
        .btn-group {{
          display: flex;
          gap: 12px;
          margin-top: 24px;
        }}
        
        .btn {{
          padding: 14px 28px;
          border-radius: 10px;
          font-size: 15px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.3s;
          border: none;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
        }}
        
        .btn-primary {{
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          flex: 1;
        }}
        
        .btn-primary:hover {{
          transform: translateY(-2px);
          box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
        }}
        
        .btn-secondary {{
          background: white;
          color: #667eea;
          border: 2px solid #667eea;
          flex: 1;
        }}
        
        .btn-secondary:hover {{
          background: #667eea;
          color: white;
        }}
        
        .btn-link {{
          background: #e5e7eb;
          color: #374151;
          padding: 10px 20px;
          text-decoration: none;
        }}
        
        .btn-link:hover {{
          background: #d1d5db;
        }}
        
        /* Auth Box */
        .auth-box {{
          background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
          border: 2px solid #e2e8f0;
          border-radius: 16px;
          padding: 24px;
          margin-bottom: 32px;
          text-align: center;
        }}
        
        .auth-box.authenticated {{
          background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
          border-color: #6ee7b7;
        }}
        
        .auth-status {{
          font-size: 16px;
          font-weight: 600;
          margin-bottom: 12px;
        }}
        
        .features-list {{
          background: #f9fafb;
          border: 1px solid #e5e7eb;
          padding: 24px;
          border-radius: 12px;
          margin-top: 32px;
        }}
        
        .features-list h3 {{
          margin: 0 0 12px 0;
          font-size: 18px;
          color: #374151;
        }}
        
        .features-list ul {{
          margin: 0;
          padding-left: 20px;
          color: #6b7280;
          font-size: 14px;
          line-height: 1.8;
        }}
        
        @media (max-width: 768px) {{
          .form-row {{
            grid-template-columns: 1fr;
          }}
          
          .license-content {{
            grid-template-columns: 1fr;
          }}
          
          .btn-group {{
            flex-direction: column;
          }}
          
          .nav-links {{
            display: none;
          }}
        }}
      </style>
    </head>
    <body>
      <!-- Header -->
      <header>
        <nav>
          <div class="logo">🎙️ Clipnote</div>
          <div class="nav-links">
            <a href="/" class="btn-link">Home</a>
            <a href="/meetings" class="btn-link">Meetings</a>
            {"<a href='/activate' class='btn btn-secondary' style='padding:8px 20px;font-size:14px;'>Activate License</a>" if not logged_in else ""}
          </div>
        </nav>
      </header>

      <div class="container">
        <div class="page-header">
          <h1>Upload Your Meeting</h1>
          <p>AI-powered transcription and summarization in minutes</p>
        </div>

        <!-- Auth Status -->
        {"<div class='auth-box authenticated'><div class='auth-status'>✅ You are logged in and ready to upload</div><form action='/auth/logout' method='post' style='display:inline'><input type='hidden' name='next_path' value='/upload-test' /><button type='submit' class='btn-link'>Logout</button></form></div>" if logged_in else "<div class='auth-box'><div class='auth-status'>🔒 Please log in to continue</div><p style='color:#718096;margin-bottom:16px;'>You need to be authenticated to upload meetings</p><a href='/login' class='btn btn-primary' style='padding:12px 24px;'>Login Now</a></div>"}

        <!-- License Widget -->
        <div class="license-widget" id="licenseWidget">
          <div style="text-align:center;opacity:0.8;">Loading license info...</div>
        </div>

        <!-- From Transcript Form -->
        <div class="card">
          <div class="card-header">
            <h2>From Transcript (No Audio)</h2>
            <div class="feature-badges">
              <span class="feature-badge">✨ AI Summarization</span>
            </div>
          </div>
        
          <form id="textForm">
            <div class="form-group">
              <label>Meeting Title</label>
              <input type="text" name="title" required placeholder="e.g., Weekly Team Standup" />
            </div>

            <div class="form-group">
              <label>Transcript</label>
              <textarea name="transcript" rows="10" placeholder="Paste your transcript here..." required></textarea>
              <div class="help-text">Paste the full meeting transcript for AI analysis</div>
            </div>

            <div class="form-group">
              <label>Email results to (optional)</label>
              <input type="email" name="email_to" placeholder="you@company.com" />
            </div>

            <div class="btn-group">
              <button type="button" class="btn btn-primary" onclick="submitTranscriptForm()" style="flex:1;">
                ✨ Analyze & Summarize
              </button>
            </div>
            <p style="font-size:13px;color:#718096;margin-top:12px;text-align:center;">
              Get executive summary, key decisions, and action items
            </p>
          </form>
        </div>

        <!-- Upload Audio/Video Form -->
        <div class="card">
          <div class="card-header">
            <h2>Upload Meeting (Audio/Video)</h2>
            <div class="feature-badges">
              <span class="feature-badge">🎯 AI-Powered</span>
              <span class="feature-badge">🌍 Multi-Language</span>
            </div>
          </div>
          <p class="subtitle">Upload audio or video files for automatic transcription and AI summarization.</p>
          
          <form id="uploadForm" enctype="multipart/form-data">
            <div class="form-row">
              <div class="form-group">
                <label>Meeting Title</label>
                <input type="text" name="title" required placeholder="e.g., Sales Call with Acme Corp" />
              </div>
              <div class="form-group">
                <label>Email results to (optional)</label>
                <input type="email" name="email_to" placeholder="you@company.com" />
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Language 🌍</label>
                <select name="language" id="languageSelect">
                  <option value="">Auto-detect</option>
                  <option value="en" selected>English</option>
                  <option value="es">Spanish (Español)</option>
                  <option value="fr">French (Français)</option>
                  <option value="de">German (Deutsch)</option>
                  <option value="it">Italian (Italiano)</option>
                  <option value="pt">Portuguese (Português)</option>
                  <option value="nl">Dutch (Nederlands)</option>
                  <option value="pl">Polish (Polski)</option>
                  <option value="ru">Russian (Русский)</option>
                  <option value="ja">Japanese (日本語)</option>
                  <option value="zh">Chinese (中文)</option>
                  <option value="ko">Korean (한국어)</option>
                  <option value="ar">Arabic (العربية)</option>
                  <option value="hi">Hindi (हिन्दी)</option>
                  <option value="tr">Turkish (Türkçe)</option>
                  <option value="sv">Swedish (Svenska)</option>
                  <option value="da">Danish (Dansk)</option>
                  <option value="no">Norwegian (Norsk)</option>
                  <option value="fi">Finnish (Suomi)</option>
                </select>
              </div>
              <div class="form-group">
                <label>Hints / Terminology (optional)</label>
                <input type="text" name="hints" placeholder="e.g., Alice, Bob, OKR, Salesforce" />
                <div class="help-text">Comma-separated names, acronyms, or industry jargon</div>
              </div>
            </div>

            <div class="form-group">
              <label>Audio/Video File</label>
              <input type="file" name="file" accept="audio/*,video/mp4" required />
              <div class="help-text">Supported formats: .mp3, .m4a, .wav, .mp4</div>
            </div>

            <div class="btn-group">
              <button type="button" class="btn btn-secondary" onclick="submitUploadForm('transcribe')">
                📝 Transcribe Only
              </button>
              <button type="button" class="btn btn-primary" onclick="submitUploadForm('summarize')">
                🚀 Transcribe & Summarize
              </button>
            </div>
          </form>
        </div>

        <!-- Features List -->
        <div class="features-list">
          <h3>✨ Features Available:</h3>
          <ul>
            <li>AI-powered transcription using AssemblyAI/Whisper</li>
            <li>Support for 19+ languages with auto-detection</li>
            <li>Custom terminology recognition for industry-specific terms</li>
            <li>Automatic summarization with key decisions and action items</li>
            <li>Email delivery of professional meeting summaries</li>
          </ul>
        </div>
      </div>

      <script>
        // License widget loading
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

        // Transcript form submission
        async function submitTranscriptForm(mode) {{
          const form = document.getElementById('textForm');
          const formData = new FormData(form);
          
          const endpoint = mode === 'transcribe' 
            ? '/meetings/transcribe-only' 
            : '/meetings/from-text';
          
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
        }}

        // Upload form submission
        async function submitUploadForm(mode) {{
          const form = document.getElementById('uploadForm');
          const formData = new FormData(form);
          
          // Add mode parameter
          formData.append('mode', mode);
          
          const endpoint = mode === 'transcribe' 
            ? '/meetings/upload-transcribe-summarize' 
            : '/meetings/upload';
          
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
        }}
        
        // Initialize
        {"loadLicenseInfo();" if logged_in else ""}
      </script>
    </body>
    </html>
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
      background: #f7fafc;
    }
    .container {
      max-width: 900px;
      margin: 0 auto;
      background: white;
      border-radius: 16px;
      padding: 32px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    h1 {
      margin: 0 0 8px 0;
      font-size: 28px;
      color: #1a202c;
    }
    .status-badge {
      display: inline-block;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 24px;
    }
    .status-processing { background: #fef3c7; color: #92400e; }
    .status-delivered { background: #d1fae5; color: #065f46; }
    .status-failed { background: #fee2e2; color: #991b1b; }
    .status-queued { background: #e0e7ff; color: #3730a3; }
    
    .progress-section {
      margin: 24px 0;
    }
    .progress-bar-container {
      width: 100%;
      height: 28px;
      background: #e5e7eb;
      border-radius: 14px;
      overflow: hidden;
      margin: 16px 0;
    }
    .progress-bar {
      height: 100%;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      transition: width 0.3s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: 13px;
      font-weight: 700;
    }
    .step-text {
      color: #6b7280;
      font-size: 15px;
      margin-top: 12px;
    }
    
    /* Summarize prompt */
    .summarize-prompt {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 24px;
      border-radius: 12px;
      margin: 24px 0;
      display: none;
    }
    .summarize-prompt.visible {
      display: block;
    }
    .summarize-prompt h3 {
      margin: 0 0 8px 0;
      font-size: 20px;
    }
    .summarize-prompt p {
      margin: 0 0 16px 0;
      opacity: 0.95;
    }
    
    .results-section {
      margin-top: 32px;
      display: none;
    }
    .results-section.visible {
      display: block;
    }
    
    .section-title {
      font-size: 20px;
      font-weight: 600;
      margin: 32px 0 16px 0;
      color: #111827;
    }
    
    .summary-box {
      background: #f9fafb;
      border: 2px solid #e5e7eb;
      border-radius: 12px;
      padding: 20px;
      margin: 12px 0;
      white-space: pre-wrap;
      line-height: 1.7;
    }
    
    .transcript-box {
      background: #f9fafb;
      border: 2px solid #e5e7eb;
      border-radius: 12px;
      padding: 20px;
      margin: 12px 0;
      white-space: pre-wrap;
      line-height: 1.7;
      max-height: 400px;
      overflow-y: auto;
    }
    
    .decisions-list {
      list-style: none;
      padding: 0;
    }
    .decisions-list li {
      padding: 12px 18px;
      background: #fef3c7;
      border-left: 4px solid #f59e0b;
      margin: 10px 0;
      border-radius: 6px;
    }
    
    .action-items-table {
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0;
    }
    .action-items-table th {
      background: #f3f4f6;
      padding: 12px;
      text-align: left;
      font-weight: 600;
      font-size: 14px;
      color: #374151;
    }
    .action-items-table td {
      padding: 12px;
      border-bottom: 1px solid #e5e7eb;
    }
    .action-items-table tr:last-child td {
      border-bottom: none;
    }
    .priority-high { 
      display: inline-block;
      padding: 3px 10px;
      background: #fee2e2;
      color: #991b1b;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
    }
    .priority-medium { 
      display: inline-block;
      padding: 3px 10px;
      background: #fef3c7;
      color: #92400e;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
    }
    .priority-low { 
      display: inline-block;
      padding: 3px 10px;
      background: #e0e7ff;
      color: #3730a3;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
    }
    
    .email-form {
      background: #f9fafb;
      border: 2px solid #e5e7eb;
      border-radius: 12px;
      padding: 24px;
      margin: 20px 0;
    }
    .form-group {
      margin-bottom: 16px;
    }
    .form-group label {
      display: block;
      margin-bottom: 8px;
      font-weight: 600;
      font-size: 14px;
      color: #374151;
    }
    .form-group input {
      width: 100%;
      padding: 12px;
      border: 2px solid #e2e8f0;
      border-radius: 10px;
      font-size: 15px;
      box-sizing: border-box;
    }
    .form-group input:focus {
      outline: none;
      border-color: #667eea;
      box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    .btn {
      padding: 12px 24px;
      border: none;
      border-radius: 10px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.3s;
    }
    .btn-primary {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
    }
    .btn-primary:hover {
      transform: translateY(-2px);
      box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
    }
    .btn-secondary {
      background: white;
      color: #667eea;
      border: 2px solid #667eea;
      margin-left: 10px;
    }
    .btn-secondary:hover {
      background: #667eea;
      color: white;
    }
    
    .download-links {
      margin: 16px 0;
    }
    .download-links a {
      display: inline-block;
      padding: 10px 20px;
      background: #f3f4f6;
      color: #374151;
      text-decoration: none;
      border-radius: 10px;
      margin-right: 10px;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s;
    }
    .download-links a:hover {
      background: #e5e7eb;
      transform: translateY(-1px);
    }
    
    .alert {
      padding: 14px 18px;
      border-radius: 10px;
      margin: 12px 0;
      font-size: 14px;
    }
    .alert-success {
      background: #d1fae5;
      color: #065f46;
      border: 2px solid #6ee7b7;
    }
    .alert-error {
      background: #fee2e2;
      color: #991b1b;
      border: 2px solid #fca5a5;
    }
    
    .spinner {
      display: inline-block;
      width: 14px;
      height: 14px;
      border: 2px solid #f3f4f6;
      border-top: 2px solid currentColor;
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
    
    <!-- Summarize Prompt (shown after transcription) -->
    <div class="summarize-prompt" id="summarizePrompt">
      <h3>✨ Transcription Complete!</h3>
      <p>Your transcript is ready. Would you like to generate an AI-powered summary with key decisions and action items?</p>
      <button class="btn btn-primary" onclick="triggerSummarization()">
        🚀 Generate Summary
      </button>
      <button class="btn btn-secondary" onclick="document.getElementById('summarizePrompt').classList.remove('visible')">
        Maybe Later
      </button>
    </div>
    
    <div class="results-section" id="resultsSection">
      
      <!-- Transcript Section (always show if available) -->
      <div id="transcriptSection" style="display:none;">
        <div class="section-title">📝 Transcript</div>
        <div class="transcript-box" id="transcriptText"></div>
      </div>
      
      <!-- Summary Section (only show if summarized) -->
      <div id="summarySection" style="display:none;">
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
      </div>
      
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
    let hasTranscript = false;
    let hasSummary = false;
    
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
          
          // Check what we have
          hasTranscript = !!meeting.transcript_path;
          hasSummary = !!meeting.summary_path;
          
          // Show appropriate content
          if (hasTranscript) {
            await fetchTranscript(meeting);
          }
          
          if (hasSummary) {
            await fetchResults(meeting);
          } else if (hasTranscript && meeting.status === 'delivered') {
            // Show summarize prompt
            document.getElementById('summarizePrompt').classList.add('visible');
          }
        }
      } catch (error) {
        console.error('Error fetching meeting status:', error);
      }
    }
    
    function updateUI(meeting) {
      document.getElementById('meetingTitle').textContent = meeting.title;
      
      const statusBadge = document.getElementById('statusBadge');
      statusBadge.textContent = meeting.status.toUpperCase();
      statusBadge.className = `status-badge status-${meeting.status}`;
      
      const progress = meeting.progress || 0;
      const progressBar = document.getElementById('progressBar');
      progressBar.style.width = `${progress}%`;
      progressBar.textContent = `${progress}%`;
      
      const stepText = document.getElementById('stepText');
      if (meeting.step) {
        stepText.innerHTML = `<span class="spinner"></span>${meeting.step}`;
      }
      
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
    
    async function fetchTranscript(meeting) {
      try {
        const response = await fetch(`/meetings/${meetingId}/download/transcript`, {
          credentials: 'include'
        });
        
        if (response.ok) {
          const text = await response.text();
          document.getElementById('transcriptText').textContent = text;
          document.getElementById('transcriptSection').style.display = 'block';
          document.getElementById('resultsSection').classList.add('visible');
        }
      } catch (error) {
        console.error('Error fetching transcript:', error);
      }
    }
    
    async function fetchResults(meeting) {
      try {
        const response = await fetch(`/meetings/${meetingId}/summary`, {
          credentials: 'include'
        });
        
        if (!response.ok) return;
        
        const summary = await response.json();
        displayResults(summary);
        
        if (meeting.email_to) {
          document.getElementById('emailInput').value = meeting.email_to;
        }
      } catch (error) {
        console.error('Error fetching results:', error);
      }
    }
    
    function displayResults(summary) {
      document.getElementById('resultsSection').classList.add('visible');
      document.getElementById('summarySection').style.display = 'block';
      
      const execSummary = summary.executive_summary || 'No summary available';
      document.getElementById('executiveSummary').textContent = execSummary;
      
      const decisionsList = document.getElementById('decisionsList');
      const decisions = summary.key_decisions || [];
      if (decisions.length === 0) {
        decisionsList.innerHTML = '<li>No key decisions recorded</li>';
      } else {
        decisionsList.innerHTML = decisions.map(d => `<li>${d}</li>`).join('');
      }
      
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
    
    async function triggerSummarization() {
      const prompt = document.getElementById('summarizePrompt');
      prompt.innerHTML = '<p style="text-align:center;"><span class="spinner"></span> Generating summary...</p>';
      
      try {
        const response = await fetch(`/meetings/${meetingId}/summarize`, {
          method: 'POST',
          credentials: 'include'
        });
        
        if (!response.ok) throw new Error('Failed to start summarization');
        
        prompt.classList.remove('visible');
        document.getElementById('progressSection').style.display = 'block';
        
        // Restart polling
        pollInterval = setInterval(fetchMeetingStatus, 2000);
        
      } catch (error) {
        prompt.innerHTML = '<p style="color:#fee2e2;">Failed to start summarization. Please try again.</p>';
        console.error('Error starting summarization:', error);
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
    
    # Use the modern meetings page HTML
    html_path = Path(__file__).parent / "templates" / "meetings.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    
    # Inline fallback - copy the HTML from the artifact above
    return """
    <!-- Paste the entire HTML from the artifact here -->
    """
       
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(meetings.router)

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Login - Clipnote</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
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
      max-width: 480px;
      width: 100%;
      padding: 48px 40px;
    }
    
    .logo {
      text-align: center;
      margin-bottom: 32px;
    }
    
    .logo-text {
      font-size: 32px;
      font-weight: 700;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      background-clip: text;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 8px;
    }
    
    .logo-subtitle {
      color: #718096;
      font-size: 15px;
    }
    
    h1 {
      font-size: 28px;
      margin-bottom: 8px;
      color: #1a202c;
      text-align: center;
    }
    
    .subtitle {
      color: #718096;
      margin-bottom: 32px;
      font-size: 15px;
      text-align: center;
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
      padding: 14px 16px;
      border: 2px solid #e2e8f0;
      border-radius: 10px;
      font-size: 16px;
      transition: all 0.2s;
      font-family: inherit;
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
      border-radius: 10px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.3s;
      margin-top: 8px;
    }
    
    .btn:hover {
      transform: translateY(-2px);
      box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
    }
    
    .btn-secondary {
      background: white;
      color: #667eea;
      border: 2px solid #e2e8f0;
      margin-top: 12px;
    }
    
    .btn-secondary:hover {
      background: #f7fafc;
      border-color: #667eea;
    }
    
    .help-text {
      margin-top: 24px;
      font-size: 13px;
      color: #718096;
      text-align: center;
      line-height: 1.6;
    }
    
    .help-text a {
      color: #667eea;
      text-decoration: none;
      font-weight: 600;
    }
    
    .help-text a:hover {
      text-decoration: underline;
    }
    
    .divider {
      margin: 24px 0;
      text-align: center;
      position: relative;
    }
    
    .divider::before {
      content: '';
      position: absolute;
      left: 0;
      top: 50%;
      width: 100%;
      height: 1px;
      background: #e2e8f0;
    }
    
    .divider span {
      background: white;
      padding: 0 16px;
      color: #718096;
      font-size: 13px;
      position: relative;
    }
    
    .info-box {
      background: #f7fafc;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 16px;
      margin-top: 24px;
    }
    
    .info-box strong {
      color: #2d3748;
      display: block;
      margin-bottom: 4px;
    }
    
    .info-box p {
      color: #718096;
      font-size: 13px;
      line-height: 1.5;
      margin: 0;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">
      <div class="logo-text">🎙️ Clipnote</div>
      <div class="logo-subtitle">Never miss important details</div>
    </div>
    
    <h1>Welcome Back</h1>
    <p class="subtitle">Sign in to access your meeting notes</p>
    
    <form action="/auth/web-login" method="post">
      <div class="form-group">
        <label for="username">Username</label>
        <input 
          type="text" 
          id="username" 
          name="username" 
          value="admin" 
          required
          autocomplete="username"
        >
      </div>
      
      <div class="form-group">
        <label for="password">Password</label>
        <input 
          type="password" 
          id="password" 
          name="password" 
          required
          autocomplete="current-password"
        >
      </div>
      
      <input type="hidden" name="next_path" value="/upload-test">
      
      <button type="submit" class="btn">Sign In</button>
    </form>
    
    <div class="divider">
      <span>OR</span>
    </div>
    
    <form action="/auth/logout" method="post">
      <input type="hidden" name="next_path" value="/login">
      <button type="submit" class="btn btn-secondary">Sign Out</button>
    </form>
    
    <div class="info-box">
      <strong>🔒 Secure Authentication</strong>
      <p>After login, an HttpOnly cookie is set. Your browser includes it automatically on all requests.</p>
    </div>
    
    <p class="help-text">
      Don't have an account? <a href="/activate">Activate your license</a><br>
      <a href="/">← Back to Home</a>
    </p>
  </div>
</body>
</html>
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
    
# Replace the _page() function and all info page routes in main.py

def _page(title: str, body_html: str) -> HTMLResponse:
    """Modern styled page template matching homepage"""
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title} – Clipnote</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f7fafc;
      color: #1a202c;
      line-height: 1.7;
    }}
    
    /* Header */
    header {{
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(10px);
      padding: 20px 0;
      box-shadow: 0 2px 10px rgba(0,0,0,0.05);
      margin-bottom: 40px;
    }}
    
    nav {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    
    .logo {{
      font-size: 24px;
      font-weight: 700;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      background-clip: text;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      text-decoration: none;
    }}
    
    .back-btn {{
      background: #e5e7eb;
      color: #374151;
      padding: 10px 20px;
      border-radius: 8px;
      text-decoration: none;
      font-weight: 600;
      font-size: 14px;
      transition: all 0.2s;
    }}
    
    .back-btn:hover {{
      background: #d1d5db;
      transform: translateY(-1px);
    }}
    
    /* Content */
    .container {{
      max-width: 800px;
      margin: 0 auto;
      padding: 0 20px 80px;
    }}
    
    .page-header {{
      text-align: center;
      margin-bottom: 48px;
    }}
    
    h1 {{
      font-size: 42px;
      color: #1a202c;
      margin-bottom: 12px;
    }}
    
    .subtitle {{
      color: #718096;
      font-size: 18px;
    }}
    
    .content-card {{
      background: white;
      border-radius: 16px;
      padding: 40px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }}
    
    .content-card h2 {{
      font-size: 28px;
      color: #1a202c;
      margin: 32px 0 16px 0;
    }}
    
    .content-card h2:first-child {{
      margin-top: 0;
    }}
    
    .content-card h3 {{
      font-size: 22px;
      color: #2d3748;
      margin: 24px 0 12px 0;
    }}
    
    .content-card p {{
      color: #4a5568;
      margin-bottom: 16px;
      line-height: 1.8;
    }}
    
    .content-card ul, .content-card ol {{
      margin: 16px 0;
      padding-left: 24px;
      color: #4a5568;
    }}
    
    .content-card li {{
      margin-bottom: 10px;
      line-height: 1.7;
    }}
    
    .content-card a {{
      color: #667eea;
      text-decoration: none;
      font-weight: 600;
    }}
    
    .content-card a:hover {{
      text-decoration: underline;
    }}
    
    .content-card strong {{
      color: #1a202c;
      font-weight: 700;
    }}
    
    .highlight-box {{
      background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
      border-left: 4px solid #667eea;
      padding: 20px;
      border-radius: 8px;
      margin: 24px 0;
    }}
    
    .contact-box {{
      background: #f7fafc;
      border: 2px solid #e2e8f0;
      border-radius: 12px;
      padding: 24px;
      margin: 32px 0;
    }}
    
    .contact-box h3 {{
      margin: 0 0 16px 0;
      color: #1a202c;
    }}
    
    .contact-item {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin: 12px 0;
      color: #4a5568;
    }}
    
    .contact-item strong {{
      min-width: 100px;
      color: #2d3748;
    }}
    
    @media (max-width: 768px) {{
      h1 {{ font-size: 32px; }}
      .content-card {{ padding: 24px; }}
    }}
  </style>
</head>
<body>
  <header>
    <nav>
      <a href="/" class="logo">🎙️ Clipnote</a>
      <a href="/" class="back-btn">← Back to Home</a>
    </nav>
  </header>
  
  <div class="container">
    <div class="page-header">
      <h1>{title}</h1>
    </div>
    <div class="content-card">
      {body_html}
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(html, media_type="text/html; charset=utf-8")


# Support Page
@app.get("/support", response_class=HTMLResponse)
def support_page():
    body = """
    <p>We're here to help! Whether you have questions about activation, uploads, or features, our support team is ready to assist.</p>
    
    <div class="contact-box">
      <h3>📧 Contact Us</h3>
      <div class="contact-item">
        <strong>Email:</strong>
        <a href="mailto:support@yourdomain.com">support@yourdomain.com</a>
      </div>
      <div class="contact-item">
        <strong>Response:</strong>
        <span>Within 24 hours on business days</span>
      </div>
    </div>
    
    <h2>Frequently Asked Questions</h2>
    
    <h3>How do I activate my license?</h3>
    <p>After purchasing, you'll receive a license key via email. Go to <a href="/activate">/activate</a>, enter your key, and you're ready to start uploading meetings!</p>
    
    <h3>What file formats are supported?</h3>
    <p>We support .mp3, .m4a, .wav for audio, and .mp4 for video files. Maximum file size depends on your tier (50MB for Starter, 200MB for Professional, 500MB for Business).</p>
    
    <h3>How accurate is the transcription?</h3>
    <p>Our AI-powered transcription uses state-of-the-art models (AssemblyAI/Whisper) with 90%+ accuracy. You can improve accuracy by providing custom terminology and hints relevant to your industry.</p>
    
    <h3>Can I edit transcripts after generation?</h3>
    <p>Currently, transcripts are delivered as-is from our AI. You can download them and edit manually. We're working on an inline editor for future releases.</p>
    
    <h3>What languages are supported?</h3>
    <p>We support 19+ languages including English, Spanish, French, German, Italian, Portuguese, Dutch, Polish, Russian, Japanese, Chinese, Korean, Arabic, Hindi, Turkish, and more. Auto-detection is also available.</p>
    
    <h3>How does email delivery work?</h3>
    <p>When you provide an email address during upload, we'll automatically send a professionally formatted summary once processing completes. You can also manually send summaries from the progress page.</p>
    
    <h3>What if my meeting fails to process?</h3>
    <p>Check your <a href="/meetings">meeting history</a>. Failed meetings show an error message. You can retry processing with one click. If issues persist, contact support with the meeting ID.</p>
    
    <div class="highlight-box">
      <strong>💡 Pro Tip:</strong> For best results, use high-quality audio recordings with minimal background noise. Provide custom terminology for technical terms or names specific to your business.
    </div>
    
    <h2>Response Times</h2>
    <ul>
      <li><strong>Starter Plan:</strong> 24-48 hours response time</li>
      <li><strong>Professional Plan:</strong> 12-24 hours response time</li>
      <li><strong>Business Plan:</strong> Priority support with 4-8 hours response time</li>
    </ul>
    
    <p>Business hours: Monday–Friday, 9am–5pm EST</p>
    """
    return _page("Support & Help", body)

# Add this route to main.py

@app.get("/documentation", response_class=HTMLResponse)
def documentation_page():
    body = """
    <div style="background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%); padding: 24px; border-radius: 12px; margin-bottom: 32px;">
      <h2 style="margin-top: 0;">Welcome to Clipnote Documentation</h2>
      <p style="margin-bottom: 0;">Everything you need to know to get the most out of your meeting transcriptions and summaries.</p>
    </div>
    
    <nav style="background: #f7fafc; padding: 20px; border-radius: 12px; margin-bottom: 32px;">
      <h3 style="margin-top: 0; font-size: 16px; color: #667eea;">Quick Navigation</h3>
      <ul style="columns: 2; gap: 20px; list-style: none; padding: 0;">
        <li><a href="#getting-started">Getting Started</a></li>
        <li><a href="#activation">License Activation</a></li>
        <li><a href="#uploading">Uploading Meetings</a></li>
        <li><a href="#transcription">Understanding Transcription</a></li>
        <li><a href="#summarization">Understanding Summaries</a></li>
        <li><a href="#languages">Multi-Language Support</a></li>
        <li><a href="#results">Reading Your Results</a></li>
        <li><a href="#email">Email Delivery</a></li>
        <li><a href="#history">Meeting History</a></li>
        <li><a href="#best-practices">Best Practices</a></li>
        <li><a href="#troubleshooting">Troubleshooting</a></li>
        <li><a href="#api">API Access</a></li>
      </ul>
    </nav>
    
    <h2 id="getting-started">🚀 Getting Started</h2>
    <p>Welcome! Here's how to get up and running in 3 simple steps:</p>
    
    <ol>
      <li><strong>Purchase a License:</strong> Choose your tier from the <a href="/#pricing">pricing page</a></li>
      <li><strong>Activate:</strong> Go to <a href="/activate">/activate</a> and enter your license key</li>
      <li><strong>Upload:</strong> Navigate to <a href="/upload-test">/upload-test</a> and start transcribing!</li>
    </ol>
    
    <div class="highlight-box">
      <strong>🎬 First Time?</strong> Try uploading a short 2-3 minute meeting first to see how it works!
    </div>
    
    <h2 id="activation">🔑 License Activation</h2>
    
    <h3>Step 1: Purchase Your License</h3>
    <p>Visit our <a href="/#pricing">pricing page</a> and select your tier:</p>
    <ul>
      <li><strong>Free:</strong> $0 free – 5 meetings/month, 25MB files</li>
      <li><strong>Starter:</strong> $29 free – 25 meetings/month, 50MB files</li>
      <li><strong>Professional:</strong> $69 one-time – 50 meetings/month, 200MB files, Cloud Storage</li>
      <li><strong>Business:</strong> $119 one-time – 100 meetings/month, 500MB files, Cloud Storage, Record Video</li>
    </ul>
    
    <h3>Step 2: Receive Your License Key</h3>
    <p>After purchase, you'll receive an email with your license key in this format:</p>
    <p style="font-family: Monaco, monospace; background: #f7fafc; padding: 12px; border-radius: 6px;">STA-XXXX-XXXX-XXXX-XXXX</p>
    
    <h3>Step 3: Activate</h3>
    <ol>
      <li>Go to <a href="/activate">/activate</a></li>
      <li>Enter your license key</li>
      <li>Click "Activate License"</li>
      <li>You'll be redirected to the upload page!</li>
    </ol>
    
    <div class="highlight-box">
      <strong>💡 Lost Your Key?</strong> Check your email (including spam folder). Still can't find it? Contact <a href="mailto:support@yourdomain.com">support@yourdomain.com</a>
    </div>
    
    <h2 id="uploading">📤 Uploading Meetings</h2>
    
    <h3>Two Ways to Upload</h3>
    
    <h4>Option 1: Upload Audio/Video Files</h4>
    <p>Perfect for recorded meetings, calls, or interviews.</p>
    <ul>
      <li><strong>Supported Formats:</strong> .mp3, .m4a, .wav, .mp4</li>
      <li><strong>File Size Limits:</strong> 25MB (Starter), 200MB (Professional), 500MB (Business)</li>
      <li><strong>Processing Time:</strong> ~1 minute per 10 minutes of audio</li>
    </ul>
    
    <h4>Option 2: Paste Existing Transcripts</h4>
    <p>Already have a transcript? Skip transcription and go straight to AI summarization.</p>
    <ul>
      <li>No file size limits</li>
      <li>Instant processing</li>
      <li>Perfect for manually transcribed meetings</li>
    </ul>
    
    <h3>Required Fields</h3>
    <ul>
      <li><strong>Title:</strong> Give your meeting a descriptive name (e.g., "Q4 Planning with Sales Team")</li>
      <li><strong>File/Transcript:</strong> Upload audio/video OR paste text transcript</li>
    </ul>
    
    <h3>Optional Fields</h3>
    <ul>
      <li><strong>Email:</strong> Receive results via email when processing completes</li>
      <li><strong>Language:</strong> Select from 19+ languages or use auto-detect</li>
      <li><strong>Hints/Terminology:</strong> Comma-separated custom terms (names, acronyms, jargon)</li>
    </ul>
    
    <h2 id="transcription">🎯 Understanding Transcription</h2>
    
    <h3>How It Works</h3>
    <ol>
      <li>Your audio is uploaded securely via TLS encryption</li>
      <li>We use AssemblyAI/Whisper AI for speech-to-text</li>
      <li>Custom terminology improves accuracy for your industry</li>
      <li>Transcript is saved and ready for download or summarization</li>
    </ol>
    
    <h3>Expected Accuracy</h3>
    <ul>
      <li><strong>High-quality audio:</strong> 90-95% accuracy</li>
      <li><strong>Standard quality:</strong> 85-90% accuracy</li>
      <li><strong>Poor quality/background noise:</strong> 70-80% accuracy</li>
    </ul>
    
    <h3>After Transcription</h3>
    <p>Once transcription completes, you'll see a prompt:</p>
    <ul>
      <li><strong>"Generate Summary"</strong> – Run AI analysis for key insights</li>
      <li><strong>"Maybe Later"</strong> – Keep transcript only, skip summarization</li>
    </ul>
    
    <h2 id="summarization">✨ Understanding Summaries</h2>
    
    <h3>What's Included</h3>
    <p>Our AI-powered summaries extract:</p>
    
    <h4>1. Executive Summary</h4>
    <p>A concise overview of the entire meeting in 2-4 sentences. Perfect for sharing with stakeholders who need the big picture.</p>
    
    <h4>2. Key Decisions</h4>
    <p>Important conclusions or agreements made during the meeting. Examples:</p>
    <ul>
      <li>"Approved $50k budget for Q2 marketing campaign"</li>
      <li>"Decided to postpone product launch to March"</li>
      <li>"Agreed on weekly check-ins every Monday at 10am"</li>
    </ul>
    
    <h4>3. Action Items</h4>
    <p>Tasks assigned during the meeting with:</p>
    <ul>
      <li><strong>Owner:</strong> Who is responsible</li>
      <li><strong>Task:</strong> What needs to be done</li>
      <li><strong>Due Date:</strong> When it's due (if mentioned)</li>
      <li><strong>Priority:</strong> High, Medium, or Low</li>
    </ul>
    
    <h3>AI Processing</h3>
    <p>We use OpenAI GPT-4 with specialized prompts to:</p>
    <ul>
      <li>Identify the most important information</li>
      <li>Extract actionable items</li>
      <li>Organize content logically</li>
      <li>Stay faithful to the original transcript (no hallucinations)</li>
    </ul>
    
    <h2 id="languages">🌍 Multi-Language Support</h2>
    
    <h3>Supported Languages</h3>
    <p>We support 19+ languages:</p>
    <ul style="columns: 2; gap: 20px;">
      <li>English</li>
      <li>Spanish (Español)</li>
      <li>French (Français)</li>
      <li>German (Deutsch)</li>
      <li>Italian (Italiano)</li>
      <li>Portuguese (Português)</li>
      <li>Dutch (Nederlands)</li>
      <li>Polish (Polski)</li>
      <li>Russian (Русский)</li>
      <li>Japanese (日本語)</li>
      <li>Chinese (中文)</li>
      <li>Korean (한국어)</li>
      <li>Arabic (العربية)</li>
      <li>Hindi (हिन्दी)</li>
      <li>Turkish (Türkçe)</li>
      <li>Swedish (Svenska)</li>
      <li>Danish (Dansk)</li>
      <li>Norwegian (Norsk)</li>
      <li>Finnish (Suomi)</li>
    </ul>
    
    <h3>Auto-Detection</h3>
    <p>Not sure what language your meeting is in? Select "Auto-detect" and our AI will identify it automatically.</p>
    
    <h3>Custom Terminology</h3>
    <p>Improve accuracy by providing industry-specific terms:</p>
    <ul>
      <li><strong>Names:</strong> Alice Chen, Robert Martinez, Sarah Johnson</li>
      <li><strong>Companies:</strong> Salesforce, Zendesk, HubSpot</li>
      <li><strong>Acronyms:</strong> OKR, KPI, API, CRM, SaaS</li>
      <li><strong>Jargon:</strong> churn rate, LTV, CAC, MRR</li>
    </ul>
    
    <h2 id="results">📊 Reading Your Results</h2>
    
    <h3>Progress Page</h3>
    <p>After upload, you'll see a real-time progress page showing:</p>
    <ul>
      <li><strong>Status:</strong> Queued → Processing → Delivered (or Failed)</li>
      <li><strong>Progress Bar:</strong> Visual indication of completion</li>
      <li><strong>Current Step:</strong> What's happening now</li>
    </ul>
    
    <h3>Viewing Results</h3>
    <p>Once complete, you'll see:</p>
    <ul>
      <li><strong>Transcript:</strong> Full text of your meeting (scrollable)</li>
      <li><strong>Executive Summary:</strong> High-level overview</li>
      <li><strong>Key Decisions:</strong> Bullet-pointed list</li>
      <li><strong>Action Items:</strong> Formatted table with owners and priorities</li>
    </ul>
    
    <h3>Download Options</h3>
    <ul>
      <li><strong>Download Transcript:</strong> Plain text .txt file</li>
      <li><strong>Download Summary:</strong> Structured JSON file</li>
    </ul>
    
    <h2 id="email">📧 Email Delivery</h2>
    
    <h3>Automatic Email</h3>
    <p>Add an email address during upload to receive automatic notifications when processing completes.</p>
    
    <h3>Manual Email</h3>
    <p>From the progress page, you can send summaries to any email address anytime.</p>
    
    <h3>Email Format</h3>
    <p>Professional HTML emails include:</p>
    <ul>
      <li>Meeting title and date</li>
      <li>Executive summary</li>
      <li>Key decisions (formatted list)</li>
      <li>Action items (formatted table)</li>
      <li>Download links for full transcript and summary</li>
    </ul>
    
    <h2 id="history">📚 Meeting History</h2>
    
    <h3>Viewing Past Meetings</h3>
    <p>Access all your meetings at <a href="/meetings">/meetings</a>. Features:</p>
    <ul>
      <li><strong>Filter by Status:</strong> All, Delivered, Processing, Failed, Queued</li>
      <li><strong>Search:</strong> Find meetings by title</li>
      <li><strong>Stats Dashboard:</strong> See total meetings and status breakdown</li>
      <li><strong>Quick Actions:</strong> View, retry failed meetings, or delete</li>
    </ul>
    
    <h3>Auto-Refresh</h3>
    <p>The meetings page auto-refreshes every 5 seconds while you have processing meetings.</p>
    
    <h2 id="best-practices">💡 Best Practices</h2>
    
    <h3>For Best Transcription Quality</h3>
    <ul>
      <li>✅ Use high-quality audio (at least 128kbps for mp3)</li>
      <li>✅ Minimize background noise</li>
      <li>✅ Use clear, audible speech</li>
      <li>✅ Avoid overlapping speakers when possible</li>
      <li>✅ Provide custom terminology for technical terms</li>
      <li>❌ Don't upload extremely long recordings (over 2 hours)</li>
      <li>❌ Avoid heavily compressed or distorted audio</li>
    </ul>
    
    <h3>For Best Summaries</h3>
    <ul>
      <li>✅ Clear meeting structure helps AI identify sections</li>
      <li>✅ Explicit decisions ("We decided to...") are easier to extract</li>
      <li>✅ Action items with owners and deadlines are captured accurately</li>
      <li>❌ Avoid rambling conversations without clear conclusions</li>
    </ul>
    
    <h3>Organizing Meetings</h3>
    <ul>
      <li>Use descriptive titles: "Q4 Budget Review" not "Meeting"</li>
      <li>Include dates or iteration numbers: "Weekly Standup #47"</li>
      <li>Use consistent naming for recurring meetings</li>
    </ul>
    
    <h2 id="troubleshooting">🔧 Troubleshooting</h2>
    
    <h3>Upload Fails</h3>
    <p><strong>Problem:</strong> File won't upload</p>
    <p><strong>Solutions:</strong></p>
    <ul>
      <li>Check file size is within your tier limit</li>
      <li>Verify file format (.mp3, .m4a, .wav, .mp4 only)</li>
      <li>Try a different browser</li>
      <li>Check your internet connection</li>
    </ul>
    
    <h3>Transcription Fails</h3>
    <p><strong>Problem:</strong> Meeting status shows "Failed"</p>
    <p><strong>Solutions:</strong></p>
    <ul>
      <li>Check if audio file is corrupted</li>
      <li>Ensure audio actually contains speech</li>
      <li>Try re-uploading with a different language setting</li>
      <li>Click "Retry" button in meeting history</li>
      <li>Contact support if issue persists</li>
    </ul>
    
    <h3>Poor Transcription Quality</h3>
    <p><strong>Problem:</strong> Transcript has many errors</p>
    <p><strong>Solutions:</strong></p>
    <ul>
      <li>Add custom terminology for names and technical terms</li>
      <li>Specify the correct language (don't rely on auto-detect)</li>
      <li>Use higher-quality audio source</li>
      <li>Reduce background noise before uploading</li>
    </ul>
    
    <h3>Email Not Received</h3>
    <p><strong>Problem:</strong> Didn't get email notification</p>
    <p><strong>Solutions:</strong></p>
    <ul>
      <li>Check spam/junk folder</li>
      <li>Verify email address was entered correctly</li>
      <li>Manually send from progress page</li>
      <li>Whitelist our sender address: no-reply@yourdomain.com</li>
    </ul>
    
    <h3>Quota Exceeded</h3>
    <p><strong>Problem:</strong> "Monthly limit reached" error</p>
    <p><strong>Solutions:</strong></p>
    <ul>
      <li>Wait until next month (quotas reset monthly)</li>
      <li>Upgrade to a higher tier</li>
      <li>Delete old meetings you no longer need</li>
    </ul>
    
    <h2 id="api">🔌 API Access (Business Tier)</h2>
    
    <h3>Authentication</h3>
    <p>Business tier includes API access. Use your license key for authentication:</p>
    <pre style="background: #f7fafc; padding: 16px; border-radius: 8px; overflow-x: auto;">
POST /meetings/upload
Headers:
  X-API-Key: YOUR-LICENSE-KEY
  Content-Type: multipart/form-data</pre>
    
    <h3>Endpoints</h3>
    <ul>
      <li><strong>POST /meetings/upload</strong> - Upload audio/video</li>
      <li><strong>POST /meetings/from-text</strong> - Submit transcript</li>
      <li><strong>GET /meetings/{id}</strong> - Get meeting status</li>
      <li><strong>GET /meetings/{id}/summary</strong> - Get summary JSON</li>
      <li><strong>GET /meetings/list</strong> - List all meetings</li>
    </ul>
    
    <h3>Testing</h3>
    <p>Use our <a href="/browser-test">API tester</a> to experiment with API calls directly in your browser.</p>
    
    <div class="highlight-box">
      <strong>📖 Full API Documentation:</strong> Business tier users receive complete API documentation with code examples in Python, JavaScript, and cURL.
    </div>
    
    <h2>Need More Help?</h2>
    <div class="contact-box">
      <p><strong>Still have questions?</strong> We're here to help!</p>
      <ul style="margin: 0; padding-left: 20px;">
        <li>📧 Email: <a href="mailto:support@yourdomain.com">support@yourdomain.com</a></li>
        <li>💬 Visit: <a href="/support">Support Center</a></li>
        <li>📚 Read: <a href="/about">About Us</a></li>
      </ul>
    </div>
    """
    return _page("Documentation", body)

# Privacy Policy
@app.get("/privacy", response_class=HTMLResponse)
def privacy_page():
    body = """
    <p class="subtitle">Last updated: January 2025</p>
    
    <h2>Information We Collect</h2>
    <p>We collect only what's necessary to provide the service:</p>
    <ul>
      <li><strong>Account Information:</strong> Email address, license tier, and activation date</li>
      <li><strong>Usage Data:</strong> Meeting counts, file sizes, processing timestamps</li>
      <li><strong>Content:</strong> Audio/video files and transcripts you upload</li>
      <li><strong>Technical Data:</strong> IP address, browser type, device info for security and reliability</li>
    </ul>
    
    <h2>How We Use Your Information</h2>
    <p>Your data is used exclusively to:</p>
    <ul>
      <li>Process transcriptions and generate meeting summaries</li>
      <li>Send email notifications with your meeting summaries</li>
      <li>Enforce license limits and prevent abuse</li>
      <li>Improve service reliability and performance</li>
      <li>Provide customer support</li>
    </ul>
    
    <div class="highlight-box">
      <strong>🔒 We never sell your data.</strong> Your meeting content and personal information are never shared with third parties for marketing or advertising purposes.
    </div>
    
    <h2>Data Storage & Security</h2>
    <ul>
      <li><strong>Encryption:</strong> All data transmitted to our servers uses TLS/SSL encryption</li>
      <li><strong>Storage:</strong> Files are stored securely with access controls and encryption at rest</li>
      <li><strong>Retention:</strong> Uploaded files may be deleted after processing (configurable). Transcripts and summaries are retained until you delete them</li>
      <li><strong>Backups:</strong> Regular backups for disaster recovery, retained for 30 days</li>
    </ul>
    
    <h2>Third-Party Services</h2>
    <p>We use trusted third-party services to provide our features:</p>
    <ul>
      <li><strong>AssemblyAI:</strong> For audio transcription (subject to their privacy policy)</li>
      <li><strong>OpenAI:</strong> For AI summarization (subject to their privacy policy)</li>
      <li><strong>Resend:</strong> For email delivery (subject to their privacy policy)</li>
    </ul>
    
    <h2>Your Rights</h2>
    <p>You have the right to:</p>
    <ul>
      <li>Access all your data</li>
      <li>Request data deletion</li>
      <li>Export your transcripts and summaries</li>
      <li>Opt-out of email communications</li>
      <li>Request correction of inaccurate information</li>
    </ul>
    
    <h2>GDPR & CCPA Compliance</h2>
    <p>We comply with GDPR (European Union) and CCPA (California) data protection requirements. If you're a resident of these jurisdictions, you have additional rights including data portability and the right to be forgotten.</p>
    
    <h2>Cookies</h2>
    <p>We use minimal cookies for:</p>
    <ul>
      <li>Authentication (secure HttpOnly cookies)</li>
      <li>Session management</li>
      <li>Remembering your preferences</li>
    </ul>
    
    <h2>Changes to This Policy</h2>
    <p>We may update this policy occasionally. Significant changes will be communicated via email. Continued use after changes constitutes acceptance.</p>
    
    <div class="contact-box">
      <h3>Questions About Privacy?</h3>
      <p>Contact our Data Protection Officer: <a href="mailto:privacy@yourdomain.com">privacy@yourdomain.com</a></p>
    </div>
    """
    return _page("Privacy Policy", body)


# Terms of Service
@app.get("/terms", response_class=HTMLResponse)
def terms_page():
    body = """
    <p class="subtitle">Last updated: January 2025</p>
    
    <h2>Agreement to Terms</h2>
    <p>By accessing and using Clipnote, you agree to be bound by these Terms of Service. If you don't agree, please do not use the service.</p>
    
    <h2>License Grant</h2>
    <p>Upon purchase and activation, we grant you a <strong>non-exclusive, non-transferable, revocable license</strong> to use Clipnote according to your purchased tier.</p>
    
    <h3>License Types:</h3>
    <ul>
      <li><strong>Starter:</strong> Single user, 5 meetings/month</li>
      <li><strong>Professional:</strong> Single user, 25 meetings/month, priority processing</li>
      <li><strong>Business:</strong> Single user or team (contact for multi-user), unlimited meetings</li>
    </ul>
    
    <div class="highlight-box">
      <strong>⚠️ Important:</strong> Licenses are non-transferable. Each license is tied to the email address used at purchase. Account sharing violates these terms and may result in license revocation.
    </div>
    
    <h2>Acceptable Use</h2>
    <p>You agree to use the service only for lawful purposes. You must NOT:</p>
    <ul>
      <li>Upload content you don't have rights to</li>
      <li>Use the service to process illegal content</li>
      <li>Attempt to reverse engineer, decompile, or hack the service</li>
      <li>Abuse rate limits or attempt to bypass restrictions</li>
      <li>Resell or redistribute our service</li>
      <li>Share your license key with others</li>
    </ul>
    
    <h2>Service Availability</h2>
    <p>We strive for 99.9% uptime but the service is provided <strong>"as is"</strong> without guarantees of:</p>
    <ul>
      <li>Uninterrupted access</li>
      <li>Error-free operation</li>
      <li>Complete data accuracy</li>
    </ul>
    <p>We reserve the right to perform maintenance, updates, and improvements that may temporarily affect availability.</p>
    
    <h2>Intellectual Property</h2>
    <p><strong>Your Content:</strong> You retain all rights to content you upload. We only use it to provide the service (transcription, summarization).</p>
    <p><strong>Our Service:</strong> All aspects of Clipnote (code, design, algorithms, branding) are our intellectual property.</p>
    
    <h2>Limitation of Liability</h2>
    <p>To the maximum extent permitted by law:</p>
    <ul>
      <li>Our total liability is limited to the amount you paid for your license</li>
      <li>We're not liable for indirect, incidental, or consequential damages</li>
      <li>We're not responsible for third-party service failures (AssemblyAI, OpenAI, Resend)</li>
    </ul>
    
    <h2>Account Termination</h2>
    <p>We may suspend or terminate your access if you:</p>
    <ul>
      <li>Violate these terms</li>
      <li>Engage in fraudulent activity</li>
      <li>Abuse the service or harm other users</li>
      <li>Fail to pay (if subscription-based features are added)</li>
    </ul>
    
    <h2>Changes to Terms</h2>
    <p>We may modify these terms with notice. Continued use after changes means acceptance. If you don't agree to new terms, stop using the service.</p>
    
    <h2>Governing Law</h2>
    <p>These terms are governed by the laws of [Your Jurisdiction]. Disputes will be resolved in courts located in [Your Location].</p>
    
    <div class="contact-box">
      <h3>Questions About Terms?</h3>
      <p>Contact legal: <a href="mailto:legal@yourdomain.com">legal@yourdomain.com</a></p>
    </div>
    """
    return _page("Terms of Service", body)


# Refund Policy
@app.get("/refunds", response_class=HTMLResponse)
def refunds_page():
    body = """
    <h2>One-Time Purchase Policy</h2>
    <p>Clipnote is a digital product sold as a <strong>one-time lifetime license</strong>. All sales are final.</p>
    
    <h2>When Refunds Are Available</h2>
    <p>We offer refunds only in these specific circumstances:</p>
    
    <h3>✅ Eligible for Refund:</h3>
    <ul>
      <li><strong>Duplicate Purchase:</strong> If you were accidentally charged twice for the same license</li>
      <li><strong>Technical Issues:</strong> If the service is completely non-functional and we cannot resolve the issue within 14 days</li>
      <li><strong>License Activation Failure:</strong> If your license key doesn't activate and we cannot provide a working replacement</li>
      <li><strong>Major Service Outage:</strong> If the service is down for more than 7 consecutive days</li>
    </ul>
    
    <h3>❌ Not Eligible for Refund:</h3>
    <ul>
      <li>Change of mind after purchase</li>
      <li>Purchased wrong tier (but we can help you upgrade)</li>
      <li>Didn't use the service</li>
      <li>Minor bugs or temporary service disruptions</li>
      <li>Dissatisfaction with AI accuracy (which depends on audio quality)</li>
      <li>After 30 days from purchase</li>
    </ul>
    
    <div class="highlight-box">
      <strong>💡 Before Purchasing:</strong> We recommend testing with a small sample meeting first. If you have questions about features or capabilities, contact support before buying.
    </div>
    
    <h2>Refund Process</h2>
    <p>If you believe you qualify for a refund:</p>
    <ol>
      <li>Contact <a href="mailto:billing@yourdomain.com">billing@yourdomain.com</a> within 30 days of purchase</li>
      <li>Provide your order number and license key</li>
      <li>Explain the issue in detail</li>
      <li>We'll investigate and respond within 3-5 business days</li>
    </ol>
    
    <p>Approved refunds are processed back to the original payment method within 7-10 business days.</p>
    
    <h2>Alternative Solutions</h2>
    <p>Before requesting a refund, consider these options:</p>
    <ul>
      <li><strong>Technical Support:</strong> Most issues can be resolved with help from our team</li>
      <li><strong>Tier Upgrade:</strong> If you need more features, we can upgrade your license (pay the difference)</li>
      <li><strong>Account Credit:</strong> In some cases, we may offer account credits instead of refunds</li>
    </ul>
    
    <h2>Chargebacks</h2>
    <p><strong>Please contact us before filing a chargeback.</strong> Chargebacks cost us significant fees and damage merchant relationships. We're committed to resolving issues fairly and will work with you to find a solution.</p>
    
    <p>If you file a chargeback without contacting us first, your license will be immediately revoked and you may be banned from future purchases.</p>
    
    <div class="contact-box">
      <h3>Billing Questions?</h3>
      <p>Email: <a href="mailto:billing@yourdomain.com">billing@yourdomain.com</a></p>
      <p>Include your order number for faster processing.</p>
    </div>
    """
    return _page("Refund Policy", body)


# About Us
@app.get("/about", response_class=HTMLResponse)
def about_page():
    body = """
    <h2>Our Mission</h2>
    <p>Clipnote was created to solve a universal problem: <strong>important details get lost in meetings</strong>. Whether it's a critical client request, a key decision, or an action item, manual note-taking is error-prone and distracting.</p>
    
    <p>We believe professionals should be <strong>fully present in conversations</strong>, not frantically scribbling notes. Our AI-powered platform captures every detail automatically, letting you focus on what matters.</p>
    
    <h2>What We Do</h2>
    <p>Clipnote provides:</p>
    <ul>
      <li><strong>Accurate Transcriptions:</strong> State-of-the-art AI converts audio/video to text in minutes</li>
      <li><strong>Smart Summaries:</strong> Automatically extract executive summaries, key decisions, and action items</li>
      <li><strong>Multi-Language Support:</strong> Process meetings in 19+ languages with custom terminology</li>
      <li><strong>Professional Delivery:</strong> Beautiful email summaries that look great in your inbox</li>
    </ul>
    
    <div class="highlight-box">
      <strong>🎯 Our Promise:</strong> Privacy-first, accurate, and fast. We never share your data and process meetings in minutes, not hours.
    </div>
    
    <h2>Who We Serve</h2>
    <p>Our platform is perfect for:</p>
    <ul>
      <li><strong>Sales Teams:</strong> Never miss a client request or follow-up action</li>
      <li><strong>Consultants:</strong> Document client meetings professionally</li>
      <li><strong>Startups:</strong> Keep your team aligned with clear meeting notes</li>
      <li><strong>Researchers:</strong> Transcribe interviews and focus groups accurately</li>
    </ul>
    
    <h2>Why Choose Us?</h2>
    <ul>
      <li><strong>One-Time Purchase:</strong> No subscriptions, no recurring charges. Buy once, use forever.</li>
      <li><strong>Privacy-First:</strong> Your data is encrypted and never sold. We're GDPR & CCPA compliant.</li>
      <li><strong>Fast Processing:</strong> Get results in minutes with our optimized pipeline</li>
      <li><strong>Great Support:</strong> Real humans ready to help with any questions</li>
    </ul>
    
    <h2>The Technology</h2>
    <p>We use cutting-edge AI models from trusted providers:</p>
    <ul>
      <li><strong>AssemblyAI & Whisper:</strong> Industry-leading speech-to-text with 90%+ accuracy</li>
      <li><strong>OpenAI GPT-4:</strong> Advanced language models for intelligent summarization</li>
      <li><strong>Custom Pipeline:</strong> Optimized processing for speed and reliability</li>
    </ul>
    
    <h2>Our Team</h2>
    <p>We're a small, focused team of engineers and designers passionate about productivity and AI. We built Clipnote because we needed it ourselves—and we think you'll love it too.</p>
    
    <div class="contact-box">
      <h3>Get in Touch</h3>
      <p>Questions or feedback? We'd love to hear from you!</p>
      <p>Email: <a href="mailto:hello@yourdomain.com">hello@yourdomain.com</a></p>
    </div>
    """
    return _page("About Us", body)


# Contact
@app.get("/contact", response_class=HTMLResponse)
def company_contact_page():
    body = """
    <h2>We're Here to Help</h2>
    <p>Have a question, suggestion, or partnership inquiry? Choose the best contact method below:</p>
    
    <div class="contact-box">
      <h3>📧 General Inquiries</h3>
      <p>For general questions about our product or company:</p>
      <p><a href="mailto:hello@yourdomain.com">hello@yourdomain.com</a></p>
    </div>
    
    <div class="contact-box">
      <h3>🛠️ Technical Support</h3>
      <p>Need help with activation, uploads, or troubleshooting?</p>
      <p><a href="mailto:support@yourdomain.com">support@yourdomain.com</a></p>
      <p><a href="/support">Visit Support Center →</a></p>
    </div>
    
    <div class="contact-box">
      <h3>💳 Billing & Licensing</h3>
      <p>Questions about purchases, refunds, or upgrades?</p>
      <p><a href="mailto:billing@yourdomain.com">billing@yourdomain.com</a></p>
    </div>
    
    <div class="contact-box">
      <h3>🤝 Partnerships</h3>
      <p>Interested in partnerships, integrations, or enterprise deals?</p>
      <p><a href="mailto:partners@yourdomain.com">partners@yourdomain.com</a></p>
    </div>
    
    <div class="contact-box">
      <h3>📰 Press & Media</h3>
      <p>Media inquiries, interviews, or press releases:</p>
      <p><a href="mailto:press@yourdomain.com">press@yourdomain.com</a></p>
    </div>
    
    <h2>Office Hours</h2>
    <p><strong>Monday – Friday:</strong> 9:00 AM – 5:00 PM EST<br>
    <strong>Weekend:</strong> Limited support (emergency issues only)</p>
    
    <h2>Social Media</h2>
    <p>Follow us for product updates, tips, and announcements:</p>
    <ul>
      <li><strong>Twitter:</strong> @aimeetingnotes</li>
      <li><strong>LinkedIn:</strong> Clipnote</li>
    </ul>
    
    <div class="highlight-box">
      <strong>💡 Quick Tip:</strong> For faster support, include your license key and a detailed description of your issue when contacting us.
    </div>
    """
    return _page("Contact Us", body)


# Blog (Placeholder)
@app.get("/blog", response_class=HTMLResponse)
def blog_stub():
    body = """
    <h2>Coming Soon</h2>
    <p>We're working on a blog with:</p>
    <ul>
      <li><strong>Productivity Tips:</strong> Best practices for meeting management</li>
      <li><strong>AI Insights:</strong> How our technology works and future improvements</li>
      <li><strong>Product Updates:</strong> New features and announcements</li>
      <li><strong>Use Cases:</strong> Real stories from our users</li>
    </ul>
    
    <div class="highlight-box">
      <strong>📬 Stay Updated:</strong> Want to be notified when we launch the blog? Email <a href="mailto:hello@yourdomain.com">hello@yourdomain.com</a> with "Blog Updates" in the subject.
    </div>
    
    <h2>In the Meantime...</h2>
    <p>Check out these resources:</p>
    <ul>
      <li><a href="/support">Support Center</a> - FAQs and troubleshooting</li>
      <li><a href="/about">About Us</a> - Learn about our mission and technology</li>
      <li><a href="/upload-test">Get Started</a> - Try the service now!</li>
    </ul>
    """
    return _page("Blog", body)
  
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)