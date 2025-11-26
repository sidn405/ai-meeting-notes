# client_portal_routes.py
import time
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
import resend
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlmodel import SQLModel, Field, Session, select
from pydantic import BaseModel
import secrets
from .portal_db import (
    get_session,
    PortalUser,
    Project,
    ProjectFile,
    ProjectMessage,
    PasswordReset,
    Review,
    Subscription,
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
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@4dgaming.games")
FROM_EMAIL = os.getenv("NOTIFICATION_FROM_EMAIL", "onboarding@resend.dev")  # Use your verified domain

# Initialize Resend client
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

FRONTEND_URL = "https://4dgaming.games"

# Subscription plan configuration
SUBSCRIPTION_PLANS = {
    'maintenance_basic': {
        'name': 'Basic Maintenance',
        'price': 497,
        'stripe_price_id': os.getenv('STRIPE_PRICE_BASIC', 'price_1SXKrx5J07OtCZ90xbFWK1b1'),
        'description': 'Essential support & hosting',
        'features': [
            'Server hosting & monitoring (99.9% uptime)',
            'Security patches & updates',
            'Bug fixes',
            'Email support (48-hour response)',
            'Monthly performance reports',
            'Database backups (weekly)',
        ]
    },
    'maintenance_pro': {
        'name': 'Professional Maintenance',
        'price': 997,
        'stripe_price_id': os.getenv('STRIPE_PRICE_PRO', 'price_1SXGABGIMdCB2CY0ZwJBkOHE'),
        'description': 'Priority support & optimization',
        'features': [
            'Everything in Basic, PLUS:',
            'Priority support (24-hour response)',
            'Phone support during business hours',
            'Monthly optimization & improvements',
            'Database backups (daily)',
            'Minor content updates (up to 2 hours/month)',
            'Quarterly strategy calls',
        ]
    },
    'maintenance_enterprise': {
        'name': 'Enterprise Maintenance',
        'price': 1997,
        'stripe_price_id': os.getenv('STRIPE_PRICE_ENTERPRISE', 'price_1SXGBJGIMdCB2CY0jsqWtIRE'),
        'description': 'White-glove service & dedicated support',
        'features': [
            'Everything in Professional, PLUS:',
            'Dedicated account manager',
            'Priority support (4-hour response)',
            '24/7 emergency phone support',
            'Weekly performance reviews',
            'Advanced analytics & insights',
            'Up to 10 hours/month development time',
            'Custom feature requests prioritized',
        ]
    }
}


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
    """Verify password - handles both bcrypt and SHA256 hashes"""
    from hashlib import sha256
    
    # Check if it's a SHA256 hash (64 hex characters)
    if len(hashed_password) == 64 and all(c in '0123456789abcdef' for c in hashed_password):
        # SHA256 hash - compare directly
        computed_hash = sha256(plain_password.encode()).hexdigest()
        return computed_hash == hashed_password
    else:
        # bcrypt hash
        truncated = plain_password[:72].encode('utf-8')
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


class SubscriptionPlanInfo(BaseModel):
    id: str
    label: str
    price: float
    interval: str
    description: str
    features: List[str]


class SubscriptionCreateRequest(BaseModel):
    project_id: int
    plan_id: str
    success_url: str
    cancel_url: str


class SubscriptionOut(BaseModel):
    id: int
    plan_id: str
    plan_name: str
    amount: float
    status: str
    stripe_subscription_id: str
    start_date: datetime
    current_period_end: Optional[datetime] = None
    next_billing_date: Optional[datetime] = None
    cancel_at_period_end: bool
    created_at: datetime
    project_id: Optional[int] = None

class SubscriptionCancelRequest(BaseModel):
    subscription_id: Optional[str] = None


# ============================================
# PYDANTIC MODELS FOR TRANSACTIONS
# ============================================

class TransactionOut(BaseModel):
    """Transaction notification model"""
    id: int
    type: str  # 'milestone_payment', 'subscription_created', 'subscription_payment'
    project_id: Optional[int] = None
    project_name: str
    client_name: str
    amount: float
    currency: str
    status: str
    stripe_payment_intent_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    created_at: datetime
    is_read: bool = False

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

# ============================================
# ADMIN NOTIFICATION ENDPOINTS
# ============================================

@router.get("/api/admin/transactions", response_model=List[TransactionOut])
async def get_admin_transactions(
    limit: int = 50,
    unread_only: bool = False,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Get all transactions for admin notification
    Combines milestone payments and subscription events
    """
    # TODO: Add admin check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    transactions = []
    
    # Get recent milestone payments from Payment table
    # Assuming you have a Payment table that tracks milestone payments
    recent_date = datetime.utcnow() - timedelta(days=30)
    
    # Get projects with recent payments
    projects = db.exec(
        select(Project)
        .where(Project.created_at >= recent_date)
        .order_by(Project.created_at.desc())
    ).all()
    
    for project in projects:
        if project.notes:
            try:
                notes = json.loads(project.notes)
                payments = notes.get('payments', [])
                
                for idx, payment in enumerate(payments):
                    if payment.get('paid_at'):
                        transactions.append(TransactionOut(
                            id=hash(f"{project.id}-milestone-{idx}") % 1000000,
                            type='milestone_payment',
                            project_id=project.id,
                            project_name=project.name,
                            client_name=project.owner.username if hasattr(project, 'owner') and project.owner else (db.get(PortalUser, project.owner_id).username if project.owner_id else 'Unknown'),
                            amount=payment.get('amount', 0),
                            currency='usd',
                            status='completed',
                            stripe_payment_intent_id=payment.get('payment_intent_id'),
                            created_at=datetime.fromisoformat(payment['paid_at'].replace('Z', '+00:00')) if isinstance(payment['paid_at'], str) else payment['paid_at'],
                            is_read=False
                        ))
            except:
                pass
    
    # Get recent subscriptions
    subscriptions = db.exec(
        select(Subscription)
        .where(Subscription.created_at >= recent_date)
        .order_by(Subscription.created_at.desc())
    ).all()
    
    for sub in subscriptions:
        # Get project name
        project = db.get(Project, sub.project_id) if sub.project_id else None
        project_name = project.name if project else f"Subscription {sub.id}"
        
        # Get client name
        user = db.get(PortalUser, sub.user_id)
        client_name = user.username if user else 'Unknown'
        
        # Subscription created event
        transactions.append(TransactionOut(
            id=hash(f"sub-created-{sub.id}") % 1000000,
            type='subscription_created',
            project_id=sub.project_id,
            project_name=project_name,
            client_name=client_name,
            amount=0,  # Setup, no charge yet
            currency=sub.currency,
            status='active',
            stripe_subscription_id=sub.stripe_subscription_id,
            created_at=sub.created_at,
            is_read=False
        ))
        
        # Subscription payment event (if has last_payment_date)
        if sub.last_payment_date:
            transactions.append(TransactionOut(
                id=hash(f"sub-payment-{sub.id}") % 1000000,
                type='subscription_payment',
                project_id=sub.project_id,
                project_name=project_name,
                client_name=client_name,
                amount=sub.amount,
                currency=sub.currency,
                status='completed',
                stripe_subscription_id=sub.stripe_subscription_id,
                created_at=sub.last_payment_date,
                is_read=False
            ))
    
    # Sort by created_at descending
    transactions.sort(key=lambda x: x.created_at, reverse=True)
    
    # Limit results
    return transactions[:limit]


@router.get("/api/admin/transactions/unread-count")
async def get_unread_transaction_count(
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get count of unread transactions for notification badge"""
    # TODO: Implement read/unread tracking in database
    # For now, return count of transactions in last 24 hours
    
    recent_date = datetime.utcnow() - timedelta(hours=24)
    
    # Count recent payments
    projects = db.exec(
        select(Project)
        .where(Project.created_at >= recent_date)
    ).all()
    
    payment_count = 0
    for project in projects:
        if project.notes:
            try:
                notes = json.loads(project.notes)
                payments = notes.get('payments', [])
                for payment in payments:
                    if payment.get('paid_at'):
                        paid_date = datetime.fromisoformat(payment['paid_at'].replace('Z', '+00:00')) if isinstance(payment['paid_at'], str) else payment['paid_at']
                        if paid_date >= recent_date:
                            payment_count += 1
            except:
                pass
    
    # Count recent subscriptions
    sub_count = db.exec(
        select(Subscription)
        .where(Subscription.created_at >= recent_date)
    ).all()
    
    total_count = payment_count + len(sub_count)
    
    return {"count": total_count}


@router.post("/api/admin/transactions/{transaction_id}/mark-read")
async def mark_transaction_read(
    transaction_id: int,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Mark a transaction as read"""
    # TODO: Implement read/unread tracking in database
    return {"success": True, "message": "Transaction marked as read"}


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

class ReviewOut(BaseModel):
    id: int
    user_name: str
    rating: int
    comment: str
    created_at: datetime
    is_approved: bool = False  # Add this field

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
        is_approved=review.is_approved,
    )


@router.get("/reviews/my-review", response_model=ReviewOut)
def get_my_review(
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Get the current user's review if it exists"""
    review = db.exec(
        select(Review).where(Review.user_id == current_user.id)
    ).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="No review found")
    
    return ReviewOut(
        id=review.id,
        user_name=current_user.name,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
        is_approved=review.is_approved,
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
                    is_approved=review.is_approved,
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
                    is_approved=review.is_approved,
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

# ========================================
# WEBHOOK HANDLER FOR SUBSCRIPTIONS
# ========================================

def handle_subscription_webhook(event_type: str, event_data: dict, db: Session):
    """Handle subscription-related webhook events"""
    
    if event_type == 'checkout.session.completed':
        session = event_data['object']
        
        if session.get('mode') == 'subscription':
            subscription_id = session.get('subscription')
            customer_id = session.get('customer')
            metadata = session.get('metadata', {})
            
            user_id = metadata.get('user_id')
            project_id = metadata.get('project_id')
            plan_id = metadata.get('plan_id')
            
            if not all([user_id, project_id, plan_id]):
                print(f"⚠️ Missing metadata in checkout session: {metadata}")
                return
            
            try:
                stripe_sub = stripe.Subscription.retrieve(subscription_id)
                plan_info = SUBSCRIPTION_PLANS.get(plan_id, {})
                
                subscription = Subscription(
                    user_id=int(user_id),
                    project_id=int(project_id),
                    stripe_subscription_id=subscription_id,
                    stripe_customer_id=customer_id,
                    stripe_price_id=stripe_sub['items']['data'][0]['price']['id'],
                    plan_id=plan_id,
                    plan_name=plan_info.get('name', plan_id),
                    amount=plan_info.get('price', 0),
                    currency='usd',
                    interval='month',
                    status=stripe_sub['status'],
                    start_date=datetime.fromtimestamp(stripe_sub['start_date']),
                    current_period_start=datetime.fromtimestamp(stripe_sub['current_period_start']),
                    current_period_end=datetime.fromtimestamp(stripe_sub['current_period_end']),
                )
                
                db.add(subscription)
                
                # Get project and user for email ✅ ADDED THIS
                project = db.get(Project, int(project_id)) if project_id else None
                user = db.get(PortalUser, int(user_id))
                
                if user and not user.stripe_customer_id:
                    user.stripe_customer_id = customer_id
                    db.add(user)
                
                db.commit()
                
                print(f"✅ Subscription created: {subscription_id} for user {user_id}")
                
                # Send email notification
                try:
                    from datetime import timedelta
                    first_charge_date = (datetime.utcnow() + timedelta(days=30)).strftime('%B %d, %Y')
                    
                    send_subscription_created_notification(
                        project_name=project.name if project else f"Subscription {subscription.id}",
                        client_name=user.username if user else 'Unknown',
                        plan_name=subscription.plan_name,
                        amount=subscription.amount,
                        subscription_id=subscription.stripe_subscription_id,
                        first_charge_date=first_charge_date
                    )
                    print(f"✅ Subscription email sent")
                except Exception as e:
                    print(f"❌ Failed to send subscription email: {e}")
                    
            except Exception as e:
                print(f"❌ Error creating subscription: {str(e)}")
    
    elif event_type == 'invoice.payment_succeeded':
        invoice = event_data['object']
        subscription_id = invoice.get('subscription')
        
        if subscription_id:
            try:
                subscription = db.exec(
                    select(Subscription)
                    .where(Subscription.stripe_subscription_id == subscription_id)
                ).first()
                
                if subscription:
                    subscription.last_payment_date = datetime.utcnow()
                    subscription.status = 'active'
                    subscription.updated_at = datetime.utcnow()
                    db.add(subscription)
                    db.commit()
                    
                    print(f"✅ Payment succeeded for subscription {subscription_id}")
                    
                    # Send email notification
                    try:
                        project = db.get(Project, subscription.project_id) if subscription.project_id else None
                        user = db.get(PortalUser, subscription.user_id)
                        
                        send_subscription_payment_notification(
                            project_name=project.name if project else f"Subscription {subscription.id}",
                            client_name=user.username if user else 'Unknown',
                            plan_name=subscription.plan_name,
                            amount=subscription.amount,
                            subscription_id=subscription.stripe_subscription_id,
                            invoice_url=event_data.get('hosted_invoice_url')
                        )
                        print(f"✅ Subscription payment email sent")
                    except Exception as e:
                        print(f"❌ Failed to send subscription payment email: {e}")
                        
            except Exception as e:
                print(f"❌ Error updating subscription payment: {str(e)}")
    
    elif event_type == 'invoice.payment_failed':
        invoice = event_data['object']
        subscription_id = invoice.get('subscription')
        
        if subscription_id:
            subscription = db.exec(
                select(Subscription)
                .where(Subscription.stripe_subscription_id == subscription_id)
            ).first()
            
            if subscription:
                subscription.status = 'past_due'
                subscription.updated_at = datetime.utcnow()
                db.add(subscription)
                db.commit()
                print(f"⚠️ Payment failed for subscription {subscription_id}")
    
    elif event_type == 'customer.subscription.updated':
        stripe_sub = event_data['object']
        subscription_id = stripe_sub.get('id')
        
        if subscription_id:
            subscription = db.exec(
                select(Subscription)
                .where(Subscription.stripe_subscription_id == subscription_id)
            ).first()
            
            if subscription:
                subscription.status = stripe_sub.get('status')
                subscription.current_period_start = datetime.fromtimestamp(stripe_sub['current_period_start'])
                subscription.current_period_end = datetime.fromtimestamp(stripe_sub['current_period_end'])
                subscription.cancel_at_period_end = stripe_sub.get('cancel_at_period_end', False)
                subscription.updated_at = datetime.utcnow()
                db.add(subscription)
                db.commit()
                print(f"✅ Subscription updated: {subscription_id}")
    
    elif event_type == 'customer.subscription.deleted':
        stripe_sub = event_data['object']
        subscription_id = stripe_sub.get('id')
        
        if subscription_id:
            subscription = db.exec(
                select(Subscription)
                .where(Subscription.stripe_subscription_id == subscription_id)
            ).first()
            
            if subscription:
                subscription.status = 'cancelled'
                subscription.cancelled_at = datetime.utcnow()
                subscription.updated_at = datetime.utcnow()
                db.add(subscription)
                db.commit()
                print(f"🚫 Subscription cancelled: {subscription_id}")


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
    
    # Handle subscription webhooks
    handle_subscription_webhook(event['type'], event['data'], db)
    
    # Handle successful payment
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Extract metadata
        project_id = session['metadata'].get('project_id')
        milestone = session['metadata'].get('milestone')
        payment_intent_id = session.get('payment_intent')  # ✅ ADDED THIS
        
        if project_id and milestone:  # ✅ Check milestone exists
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
                
                # Store payment info in project notes
                try:
                    details = json.loads(project.notes) if project.notes else {}
                    if 'payments' not in details:
                        details['payments'] = []
                    
                    details['payments'].append({
                        'milestone': int(milestone),
                        'amount': session['amount_total'] / 100,  # Convert cents to dollars
                        'paid_at': datetime.utcnow().isoformat(),
                        'stripe_session_id': session['id'],
                        'payment_status': session['payment_status'],
                        'payment_intent_id': payment_intent_id  # ✅ ADDED THIS
                    })
                    
                    project.notes = json.dumps(details)
                    db.commit()
                    
                    # ✅ SEND EMAIL NOTIFICATION (MOVED HERE - AFTER db.commit())
                    try:
                        milestone_data = details.get('pricing', {}).get('milestones', [])[int(milestone) - 1]
                        send_milestone_payment_notification(
                            project_name=project.name,
                            client_name=project.owner.username if hasattr(project, 'owner') and project.owner else (db.get(PortalUser, project.owner_id).username if project.owner_id else 'Unknown'),
                            milestone_number=int(milestone),  # ✅ Use 'milestone' not 'milestone_number'
                            milestone_name=milestone_data.get('name', f'Milestone {milestone}'),
                            amount=session['amount_total'] / 100,  # ✅ Use session data
                            payment_intent_id=payment_intent_id or session['id']  # ✅ Fallback to session ID
                        )
                        print(f"✅ Email sent for milestone {milestone} payment")
                    except Exception as e:
                        print(f"❌ Failed to send email: {e}")
                        
                except Exception as e:
                    print(f"❌ Failed to update project notes: {e}")
    
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


# ========================================
# SUBSCRIPTION ROUTES
# ========================================

@router.get("/subscriptions/plans", response_model=List[SubscriptionPlanInfo])
def get_subscription_plans():
    """Get available subscription plans"""
    return [
        SubscriptionPlanInfo(
            id=plan_id,
            label=plan['name'],
            price=plan['price'],
            interval='month',
            description=plan['description'],
            features=plan['features']
        )
        for plan_id, plan in SUBSCRIPTION_PLANS.items()
    ]


@router.post("/subscriptions/create-checkout-session")
async def create_checkout_session(
    data: SubscriptionCreateRequest,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Create a Stripe Checkout Session for subscription"""
    import time
    
    # Verify project belongs to user
    project = db.get(Project, data.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get plan details
    plan = SUBSCRIPTION_PLANS.get(data.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid subscription plan")
    
    stripe_price_id = plan["stripe_price_id"]
    if not stripe_price_id:
        raise HTTPException(status_code=500, detail="Stripe price ID not configured")
    
    try:
        # Create Stripe Checkout Session with metadata
        checkout_session = stripe.checkout.Session.create(
            mode='subscription',
            line_items=[{
                'price': stripe_price_id,
                'quantity': 1,
            }],
            success_url=data.success_url,
            cancel_url=data.cancel_url,
            customer_email=current_user.email if hasattr(current_user, 'email') else None,
            subscription_data={
                'metadata': {
                    'user_id': str(current_user.id),
                    'project_id': str(data.project_id),
                    'plan_id': data.plan_id,
                },
                'billing_cycle_anchor': int(time.time()) + (30 * 24 * 60 * 60),  # 30 days
            },
            metadata={
                'user_id': str(current_user.id),
                'project_id': str(data.project_id),
                'plan_id': data.plan_id,
            },
        )
        
        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }
        
    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")


@router.get("/subscriptions/list", response_model=List[SubscriptionOut])
def list_subscriptions(
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """List all subscriptions for the current user"""
    
    subscriptions = db.exec(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
    ).all()
    
    return [
        SubscriptionOut(
            id=sub.id,
            plan_id=sub.plan_id,
            plan_name=sub.plan_name,
            amount=sub.amount,
            status=sub.status,
            stripe_subscription_id=sub.stripe_subscription_id,
            start_date=sub.start_date,
            current_period_end=sub.current_period_end,
            next_billing_date=sub.current_period_end,
            cancel_at_period_end=sub.cancel_at_period_end,
            created_at=sub.created_at,
            project_id=sub.project_id
        )
        for sub in subscriptions
    ]


@router.post("/subscriptions/cancel")
async def cancel_subscription(
    payload: SubscriptionCancelRequest,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Cancel a subscription (at period end)"""
    
    # Find subscription by stripe_subscription_id or find active subscription
    if payload.subscription_id:
        subscription = db.exec(
            select(Subscription)
            .where(Subscription.stripe_subscription_id == payload.subscription_id)
            .where(Subscription.user_id == current_user.id)
        ).first()
    else:
        # Find any active subscription
        subscription = db.exec(
            select(Subscription)
            .where(Subscription.user_id == current_user.id)
            .where(Subscription.status == 'active')
        ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")
    
    try:
        # Cancel at period end
        updated_sub = stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        # Update database
        subscription.cancel_at_period_end = True
        subscription.updated_at = datetime.utcnow()
        db.add(subscription)
        db.commit()
        
        return {
            "success": True,
            "message": "Subscription will be cancelled at the end of the current billing period",
            "period_end": updated_sub.current_period_end
        }
        
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")


@router.post("/subscriptions/reactivate")
async def reactivate_subscription(
    payload: SubscriptionCancelRequest,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Reactivate a subscription that was set to cancel"""
    
    subscription = db.exec(
        select(Subscription)
        .where(Subscription.stripe_subscription_id == payload.subscription_id)
        .where(Subscription.user_id == current_user.id)
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    if not subscription.cancel_at_period_end:
        return {"success": True, "message": "Subscription is already active"}
    
    try:
        # Remove cancel_at_period_end flag
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=False
        )
        
        # Update database
        subscription.cancel_at_period_end = False
        subscription.updated_at = datetime.utcnow()
        db.add(subscription)
        db.commit()
        
        return {"success": True, "message": "Subscription reactivated successfully"}
        
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
def get_subscription(
    subscription_id: int,
    current_user: PortalUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Get subscription details"""
    
    subscription = db.get(Subscription, subscription_id)
    if not subscription or subscription.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    return SubscriptionOut(
        id=subscription.id,
        plan_id=subscription.plan_id,
        plan_name=subscription.plan_name,
        amount=subscription.amount,
        status=subscription.status,
        stripe_subscription_id=subscription.stripe_subscription_id,
        start_date=subscription.start_date,
        current_period_end=subscription.current_period_end,
        next_billing_date=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        created_at=subscription.created_at
    )


# ============================================
# EMAIL SENDING FUNCTION
# ============================================

def send_email_resend(to_email: str, subject: str, html_body: str):
    """Send an email using Resend API"""
    if not RESEND_API_KEY:
        print("❌ Resend API key not configured")
        return False
    
    try:
        params = {
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        }
        
        email = resend.Emails.send(params)  # ✅ Correct API call
        print(f"✅ Email sent to {to_email}: {subject}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {str(e)}")
        return False


# ============================================
# EMAIL TEMPLATES
# ============================================

def send_milestone_payment_notification(
    project_name: str,
    client_name: str,
    milestone_number: int,
    milestone_name: str,
    amount: float,
    payment_intent_id: str
):
    """Send notification when a milestone payment is received"""
    
    subject = f"💰 New Payment: {project_name} - Milestone {milestone_number}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
            .amount {{ font-size: 42px; font-weight: bold; color: #10b981; margin: 20px 0; text-align: center; }}
            .details {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .details-row {{ padding: 10px 0; border-bottom: 1px solid #e5e7eb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">🎉 Payment Received!</h1>
            </div>
            <div class="content">
                <div class="amount">${amount:.2f}</div>
                <div class="details">
                    <div class="details-row"><strong>Project:</strong> {project_name}</div>
                    <div class="details-row"><strong>Client:</strong> {client_name}</div>
                    <div class="details-row"><strong>Milestone:</strong> {milestone_number} - {milestone_name}</div>
                    <div class="details-row"><strong>Payment ID:</strong> {payment_intent_id}</div>
                </div>
                <div style="text-align: center; margin-top: 20px;">
                    <a href="https://4dgaming.games/admin-portal.html" 
                       style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                              color: white; padding: 14px 32px; text-decoration: none; 
                              border-radius: 6px; display: inline-block;">
                        View in Admin Portal
                    </a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email_resend(ADMIN_EMAIL, subject, html_body)


def send_subscription_created_notification(
    project_name: str,
    client_name: str,
    plan_name: str,
    amount: float,
    subscription_id: str,
    first_charge_date: str
):
    """Send notification when a subscription is created"""
    
    subject = f"🎯 New Subscription: {project_name} - {plan_name}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
            .amount {{ font-size: 36px; font-weight: bold; color: #8b5cf6; margin: 20px 0; text-align: center; }}
            .details {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .grace {{ background: #dbeafe; padding: 15px; border-radius: 4px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">🎉 New Subscription!</h1>
            </div>
            <div class="content">
                <div style="font-size: 24px; font-weight: bold; text-align: center; color: #8b5cf6;">{plan_name}</div>
                <div class="amount">${amount:.2f}/month</div>
                <div class="details">
                    <div><strong>Project:</strong> {project_name}</div>
                    <div><strong>Client:</strong> {client_name}</div>
                    <div><strong>Subscription ID:</strong> {subscription_id}</div>
                </div>
                <div class="grace">
                    <strong>📅 30-Day Grace Period Active</strong><br>
                    First charge: <strong>{first_charge_date}</strong>
                </div>
                <div style="text-align: center;">
                    <a href="https://4dgaming.games/admin-portal.html" 
                       style="background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%); 
                              color: white; padding: 14px 32px; text-decoration: none; 
                              border-radius: 6px; display: inline-block;">
                        View in Admin Portal
                    </a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email_resend(ADMIN_EMAIL, subject, html_body)


def send_subscription_payment_notification(
    project_name: str,
    client_name: str,
    plan_name: str,
    amount: float,
    subscription_id: str,
    invoice_url: Optional[str] = None
):
    """Send notification when a subscription payment succeeds"""
    
    subject = f"💳 Subscription Payment: {project_name} - ${amount:.2f}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
            .amount {{ font-size: 42px; font-weight: bold; color: #10b981; margin: 20px 0; text-align: center; }}
            .details {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">💰 Subscription Payment!</h1>
            </div>
            <div class="content">
                <div class="amount">${amount:.2f}</div>
                <div class="details">
                    <div><strong>Project:</strong> {project_name}</div>
                    <div><strong>Client:</strong> {client_name}</div>
                    <div><strong>Plan:</strong> {plan_name}</div>
                    <div><strong>Subscription:</strong> {subscription_id}</div>
                </div>
                <div style="text-align: center;">
                    <a href="https://4dgaming.games/admin-portal.html" 
                       style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                              color: white; padding: 14px 32px; text-decoration: none; 
                              border-radius: 6px; display: inline-block;">
                        View in Admin Portal
                    </a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email_resend(ADMIN_EMAIL, subject, html_body)


class CheckoutResponse(SQLModel):
    checkout_url: str