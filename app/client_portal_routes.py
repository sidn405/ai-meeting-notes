# client_portal_routes.py

import os
import json
import stripe
from datetime import datetime, timedelta
from typing import List, Optional
import bcrypt
import boto3
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Request,
    Response,
    Query,
    status,
)
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlmodel import SQLModel, Field, Session, select
import secrets
from .portal_db import (
    get_session,
    PortalUser,
    Project,
    ProjectFile,
    ProjectMessage,
    PasswordReset,
    Review,
)

# ---------- CONFIG ----------

SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_SUPER_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

B2_ENDPOINT_URL = os.getenv("B2_ENDPOINT_URL")  # e.g. https://s3.us-west-004.backblazeb2.com
B2_ACCESS_KEY_ID = os.getenv("B2_ACCESS_KEY_ID")
B2_SECRET_ACCESS_KEY = os.getenv("B2_SECRET_ACCESS_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME", "4dgaming-client-files")

# Add Resend configuration after other configs (around line 40)
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "noreply@4dgaming.games")

FRONTEND_URL = "https://4dgaming.games"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

s3_client = boto3.client(
    "s3",
    endpoint_url=B2_ENDPOINT_URL,
    aws_access_key_id=B2_ACCESS_KEY_ID,
    aws_secret_access_key=B2_SECRET_ACCESS_KEY,
)


MAX_BCRYPT_LEN = 72  # bcrypt limit in bytes; we'll just truncate the string



def hash_password(password: str) -> str:
    """Hash password using bcrypt directly"""
    truncated = password[:MAX_BCRYPT_LEN].encode('utf-8')
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    truncated = plain_password[:MAX_BCRYPT_LEN].encode('utf-8')
    return bcrypt.checkpw(truncated, hashed_password.encode('utf-8'))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def upload_to_b2(file_obj, key: str, content_type: str) -> str:
    s3_client.upload_fileobj(
        file_obj,
        B2_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return f"{B2_ENDPOINT_URL}/{B2_BUCKET_NAME}/{key}"


# ---------- SCHEMAS ----------

class RegisterRequest(SQLModel):
    name: str
    email: str
    password: str


class LoginRequest(SQLModel):
    email: str
    password: str


class UserOut(SQLModel):
    id: int
    name: str
    email: str
    is_admin: bool


class ProjectCreate(SQLModel):
    service: str
    name: str
    notes: Optional[str] = None


class ProjectOut(SQLModel):
    id: int
    name: str
    service: str
    status: str
    notes: Optional[str]
    created_at: datetime
    service_label: Optional[str] = None


class AdminProjectOut(ProjectOut):
    owner_name: str
    owner_email: str


class MessageCreate(SQLModel):
    body: str


class MessageOut(SQLModel):
    id: int
    sender: str
    body: str
    created_at: datetime


class FileOut(SQLModel):
    id: int
    original_name: str
    url: str
    created_at: datetime


# ---------- CURRENT USER ----------

async def get_current_user(
    request: Request,
    db: Session = Depends(get_session),
) -> PortalUser:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get(PortalUser, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_admin(current_user: PortalUser = Depends(get_current_user)) -> PortalUser:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user


# ---------- CONSTANTS ----------

SERVICE_LABELS = {
    "chatbot": "AI Chatbot Development",
    "mobile": "Mobile App Development",
    "game": "Game Development & Reskinning",
    "web3": "Web3 & Blockchain Development",
    "scraping": "Web Scraping & Lead Gen",
    "pdf": "PDF Generation Service",
    "nft": "NFT & Metaverse Assets",
    "trading": "Trading Bot Development",
}

router = APIRouter(prefix="/api", tags=["client-portal"])


# ======================
# AUTH ROUTES
# ======================

@router.post("/auth/register", response_model=UserOut)
def register_user(
    data: RegisterRequest,
    response: Response,
    db: Session = Depends(get_session),
):
    existing = db.exec(
        select(PortalUser).where(PortalUser.email == data.email.strip().lower())
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = PortalUser(
        name=data.name.strip(),
        email=data.email.strip().lower(),
        hashed_password=hash_password(data.password),
        is_admin=False,  # clients only; set admin manually in DB
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create JWT token and set cookie (same as login)
    token = create_access_token({"sub": str(user.id)})
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=True,
        samesite="none",  # Required for cross-origin
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    
    return UserOut(id=user.id, name=user.name, email=user.email, is_admin=user.is_admin)


@router.post("/auth/login", response_model=UserOut)
def login_user(
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_session),
):
    user = db.exec(
        select(PortalUser).where(PortalUser.email == data.email.strip().lower())
    ).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    token = create_access_token({"sub": str(user.id)})
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=True,
        samesite="none",  # Changed from "lax" to match register
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return UserOut(id=user.id, name=user.name, email=user.email, is_admin=user.is_admin)


@router.get("/auth/me", response_model=UserOut)
def get_me(current_user: PortalUser = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        is_admin=current_user.is_admin,
    )

# ==========================================
# PASSWORD RESET ROUTES (add to router)
# ==========================================

class ForgotPasswordRequest(SQLModel):
    email: str

class ResetPasswordRequest(SQLModel):
    token: str
    new_password: str

@router.post("/auth/forgot-password")
def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_session),
):
    """Send password reset email via Resend"""
    user = db.exec(
        select(PortalUser).where(PortalUser.email == data.email.strip().lower())
    ).first()
    
    # Always return success to prevent email enumeration
    if not user:
        return {"ok": True, "message": "If that email exists, a reset link has been sent"}
    
    # Generate reset token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    # Save to database
    reset = PasswordReset(
        email=user.email,
        token=token,
        expires_at=expires_at,
    )
    db.add(reset)
    db.commit()
    
    # Send email via Resend
    reset_link = f"{FRONTEND_URL}/reset-password.html?token={token}"
    
    try:
        import requests
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM_EMAIL,
                "to": [user.email],
                "subject": "Reset Your 4D Gaming Password",
                "html": f"""
                    <h2>Password Reset Request</h2>
                    <p>Hi {user.name},</p>
                    <p>You requested to reset your password for your 4D Gaming client portal account.</p>
                    <p>Click the link below to reset your password (valid for 1 hour):</p>
                    <p><a href="{reset_link}" style="background:#667eea;color:white;padding:12px 24px;text-decoration:none;border-radius:8px;display:inline-block;">Reset Password</a></p>
                    <p>Or copy this link: {reset_link}</p>
                    <p>If you didn't request this, you can safely ignore this email.</p>
                    <p>Thanks,<br>4D Gaming Team</p>
                """,
            },
        )
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send reset email: {e}")
        # Don't fail the request - we don't want to leak email existence
    
    return {"ok": True, "message": "If that email exists, a reset link has been sent"}


@router.post("/auth/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_session),
):
    """Reset password using token"""
    # Find valid token
    reset = db.exec(
        select(PasswordReset).where(
            PasswordReset.token == data.token,
            PasswordReset.used == False,
            PasswordReset.expires_at > datetime.utcnow(),
        )
    ).first()
    
    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    # Find user
    user = db.exec(
        select(PortalUser).where(PortalUser.email == reset.email)
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update password
    user.hashed_password = hash_password(data.new_password)
    
    # Mark token as used
    reset.used = True
    
    db.add(user)
    db.add(reset)
    db.commit()
    
    return {"ok": True, "message": "Password reset successful"}


# ==========================================
# REVIEW ROUTES (add to router)
# ==========================================

class ReviewCreate(SQLModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=10, max_length=500)

class ReviewOut(SQLModel):
    id: int
    user_name: str
    rating: int
    comment: str
    created_at: datetime

@router.post("/reviews", response_model=ReviewOut)
def create_review(
    data: ReviewCreate,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Create a new review (requires authentication)"""
    # Check if user already has a review
    existing = db.exec(
        select(Review).where(Review.user_id == current_user.id)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="You have already submitted a review")
    
    review = Review(
        user_id=current_user.id,
        rating=data.rating,
        comment=data.comment,
        is_approved=False,  # Requires admin approval
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    
    return ReviewOut(
        id=review.id,
        user_name=current_user.name,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
    )


@router.get("/reviews/public", response_model=List[ReviewOut])
def get_public_reviews(db: Session = Depends(get_session)):
    """Get all approved reviews for public display"""
    reviews = db.exec(
        select(Review).where(Review.is_approved == True).order_by(Review.created_at.desc())
    ).all()
    
    result = []
    for review in reviews:
        user = db.get(PortalUser, review.user_id)
        if user:
            result.append(
                ReviewOut(
                    id=review.id,
                    user_name=user.name,
                    rating=review.rating,
                    comment=review.comment,
                    created_at=review.created_at,
                )
            )
    
    return result


@router.get("/admin/reviews", response_model=List[ReviewOut])
def admin_list_reviews(
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """Admin: Get all reviews (approved and pending)"""
    reviews = db.exec(
        select(Review).order_by(Review.created_at.desc())
    ).all()
    
    result = []
    for review in reviews:
        user = db.get(PortalUser, review.user_id)
        if user:
            result.append(
                ReviewOut(
                    id=review.id,
                    user_name=user.name,
                    rating=review.rating,
                    comment=review.comment,
                    created_at=review.created_at,
                )
            )
    
    return result


@router.patch("/admin/reviews/{review_id}/approve")
def admin_approve_review(
    review_id: int,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """Admin: Approve a review"""
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    review.is_approved = True
    db.add(review)
    db.commit()
    
    return {"ok": True}


@router.delete("/admin/reviews/{review_id}")
def admin_delete_review(
    review_id: int,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """Admin: Delete a review"""
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    db.delete(review)
    db.commit()
    
    return {"ok": True}

# ======================
# PROJECT HELPERS
# ======================

def get_project_or_404(
    project_id: int,
    current_user: PortalUser,
    db: Session,
) -> Project:
    project = db.get(Project, project_id)
    # allow owner OR admin
    if not project or (project.owner_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ======================
# CLIENT PROJECT ROUTES
# ======================

@router.get("/projects", response_model=List[ProjectOut])
def list_projects(
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    projects = db.exec(
        select(Project)
        .where(Project.owner_id == current_user.id)
        .order_by(Project.created_at.desc())
    ).all()
    out: List[ProjectOut] = []
    for p in projects:
        out.append(
            ProjectOut(
                id=p.id,
                name=p.name,
                service=p.service,
                status=p.status,
                notes=p.notes,
                created_at=p.created_at,
                service_label=SERVICE_LABELS.get(p.service),
            )
        )
    return out


@router.post("/projects", response_model=ProjectOut)
def create_project(
    payload: ProjectCreate,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    project = Project(
        owner_id=current_user.id,
        name=payload.name.strip(),
        service=payload.service,
        notes=payload.notes,
        status="pending",
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return ProjectOut(
        id=project.id,
        name=project.name,
        service=project.service,
        status=project.status,
        notes=project.notes,
        created_at=project.created_at,
        service_label=SERVICE_LABELS.get(project.service),
    )

# ======================
# STRIPE CHECKOUT - MILESTONE PAYMENTS
# ======================

@router.post("/projects/{project_id}/checkout")
async def create_milestone_checkout(
    project_id: int,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
    milestone: Optional[int] = Query(None, description="Milestone number to pay for"),
):
    """Create Stripe Checkout session for milestone payment"""
    # Debug logging
    print(f"🔍 Checkout called - Project: {project_id}, Milestone param: {milestone}")
    
    project = get_project_or_404(project_id, current_user, db)
    
    # Parse project details to get milestone info
    try:
        details = json.loads(project.notes) if project.notes else {}
    except json.JSONDecodeError:
        details = {}
    
    pricing = details.get('pricing') or {}
    milestones = pricing.get('milestones', [])
    payments = details.get('payments', [])
    
    if not milestones:
        raise HTTPException(
            status_code=400,
            detail="No milestones found for this project. Please contact support."
        )
    
    # Determine which milestone to pay for
    if milestone is None:
        # Calculate next unpaid milestone
        paid_milestones = [p.get('milestone') for p in payments]
        next_milestone_num = max(paid_milestones, default=0) + 1
        print(f"📊 No milestone specified, calculated next: {next_milestone_num} (paid: {paid_milestones})")
    else:
        next_milestone_num = milestone
        print(f"✅ Using specified milestone: {next_milestone_num}")
    
    print(f"🎯 Final milestone to charge: {next_milestone_num}")
    
    # Validate milestone number
    if next_milestone_num < 1 or next_milestone_num > len(milestones):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid milestone number. Must be between 1 and {len(milestones)}"
        )
    
    # Check if milestone already paid
    paid_milestones = [p.get('milestone') for p in payments]
    if next_milestone_num in paid_milestones:
        raise HTTPException(
            status_code=400,
            detail=f"Milestone {next_milestone_num} has already been paid"
        )
    
    # Get milestone details
    milestone_data = milestones[next_milestone_num - 1]
    amount = milestone_data.get('amount', 0)
    milestone_name = milestone_data.get('name', f'Milestone {next_milestone_num}')
    milestone_week = milestone_data.get('weeksFromStart', next_milestone_num)
    
    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid milestone amount"
        )
    
    try:
        # Create Stripe Checkout Session with dynamic pricing
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card', 'cashapp', 'affirm', 'klarna'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': int(amount * 100),  # Convert dollars to cents
                    'product_data': {
                        'name': f"4D Gaming - {project.name}",
                        'description': f"Milestone {next_milestone_num}: {milestone_name} (Week {milestone_week})",
                        'metadata': {
                            'project_id': str(project_id),
                            'milestone_number': str(next_milestone_num),
                            'business': '4D Gaming'
                        }
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{FRONTEND_URL}/client-portal?payment=success&project_id={project_id}",
            cancel_url=f"{FRONTEND_URL}/client-portal?payment=cancelled&project_id={project_id}",
            customer_email=current_user.email,
            metadata={
                'project_id': str(project_id),
                'milestone': str(next_milestone_num),
                'user_id': str(current_user.id),
                'user_email': current_user.email,
                'user_name': current_user.name,
                'business': '4D Gaming',
                'project_name': project.name
            },
            # Add custom branding text
            custom_text={
                'submit': {
                    'message': f'Complete payment for {project.name} - Milestone {next_milestone_num}'
                }
            }
        )
        
        return {
            'checkout_url': checkout_session.url,
            'session_id': checkout_session.id
        }
        
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Stripe error: {str(e)}"
        )


# ======================
# STRIPE WEBHOOK HANDLER
# ======================

@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_session)
):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle successful payment
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Extract metadata
        project_id = session['metadata'].get('project_id')
        milestone = session['metadata'].get('milestone')
        
        if project_id:
            # Update project status
            project = db.get(Project, int(project_id))
            if project:
                # Update status based on milestone
                if milestone == '1':
                    project.status = 'in-progress'
                elif milestone == '2':
                    project.status = 'in-progress'
                elif milestone == '3':
                    project.status = 'completed'
                
                # You could also store payment info in project notes
                try:
                    details = json.loads(project.notes) if project.notes else {}
                    if 'payments' not in details:
                        details['payments'] = []
                    
                    details['payments'].append({
                        'milestone': int(milestone),
                        'amount': session['amount_total'] / 100,  # Convert cents to dollars
                        'paid_at': datetime.utcnow().isoformat(),
                        'stripe_session_id': session['id'],
                        'payment_status': session['payment_status']
                    })
                    
                    project.notes = json.dumps(details)
                except:
                    pass  # Don't fail if notes update fails
                
                db.commit()
    
    return {"status": "success"}

# ======================
# ADMIN PROJECT ROUTES
# ======================

@router.get("/admin/projects", response_model=List[AdminProjectOut])
def admin_list_projects(
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    projects = db.exec(select(Project).order_by(Project.created_at.desc())).all()
    out: List[AdminProjectOut] = []
    for p in projects:
        owner = db.get(PortalUser, p.owner_id)
        out.append(
            AdminProjectOut(
                id=p.id,
                name=p.name,
                service=p.service,
                status=p.status,
                notes=p.notes,
                created_at=p.created_at,
                service_label=SERVICE_LABELS.get(p.service),
                owner_name=owner.name if owner else "Unknown",
                owner_email=owner.email if owner else "unknown",
            )
        )
    return out


class StatusUpdate(SQLModel):
    status: str


@router.patch("/admin/projects/{project_id}/status", response_model=ProjectOut)
def admin_update_status(
    project_id: int,
    payload: StatusUpdate,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.status = payload.status
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectOut(
        id=project.id,
        name=project.name,
        service=project.service,
        status=project.status,
        notes=project.notes,
        created_at=project.created_at,
        service_label=SERVICE_LABELS.get(project.service),
    )


# ======================
# FILES
# ======================

@router.get("/projects/{project_id}/files", response_model=List[FileOut])
def list_files(
    project_id: int,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    _ = get_project_or_404(project_id, current_user, db)
    files = db.exec(
        select(ProjectFile)
        .where(ProjectFile.project_id == project_id)
        .order_by(ProjectFile.created_at)
    ).all()
    return [
        FileOut(id=f.id, original_name=f.original_name, url=f.url, created_at=f.created_at)
        for f in files
    ]


@router.post("/projects/{project_id}/files", response_model=List[FileOut])
async def upload_files(
    project_id: int,
    files: List[UploadFile] = File(...),
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    project = get_project_or_404(project_id, current_user, db)
    created: List[FileOut] = []

    for uf in files:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        safe_name = uf.filename.replace(" ", "_")
        key = f"projects/{project.id}/{timestamp}_{safe_name}"

        uf.file.seek(0)
        url = upload_to_b2(uf.file, key, uf.content_type or "application/octet-stream")

        pf = ProjectFile(
            project_id=project.id,
            original_name=uf.filename,
            s3_key=key,
            url=url,
        )
        db.add(pf)
        db.commit()
        db.refresh(pf)
        created.append(
            FileOut(
                id=pf.id,
                original_name=pf.original_name,
                url=pf.url,
                created_at=pf.created_at,
            )
        )

    return created


# ======================
# MESSAGES
# ======================

@router.get("/projects/{project_id}/messages", response_model=List[MessageOut])
def list_messages(
    project_id: int,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    _ = get_project_or_404(project_id, current_user, db)
    msgs = db.exec(
        select(ProjectMessage)
        .where(ProjectMessage.project_id == project_id)
        .order_by(ProjectMessage.created_at)
    ).all()
    return [
        MessageOut(id=m.id, sender=m.sender, body=m.body, created_at=m.created_at)
        for m in msgs
    ]


@router.post("/projects/{project_id}/messages", response_model=MessageOut)
def create_message(
    project_id: int,
    payload: MessageCreate,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    project = get_project_or_404(project_id, current_user, db)
    msg = ProjectMessage(
        project_id=project.id,
        sender="client",
        body=payload.body,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return MessageOut(id=msg.id, sender=msg.sender, body=msg.body, created_at=msg.created_at)


@router.post("/admin/projects/{project_id}/messages", response_model=MessageOut)
def admin_create_message(
    project_id: int,
    payload: MessageCreate,
    current_user: PortalUser = Depends(require_admin),
    db: Session = Depends(get_session),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    msg = ProjectMessage(
        project_id=project.id,
        sender="owner",
        body=payload.body,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return MessageOut(id=msg.id, sender=msg.sender, body=msg.body, created_at=msg.created_at)

class CheckoutResponse(SQLModel):
    checkout_url: str