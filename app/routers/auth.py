# app/routers/auth.py
from fastapi import APIRouter, HTTPException, Form, Depends
from pydantic import BaseModel
from fastapi.responses import RedirectResponse, JSONResponse
import hmac, os
from ..config import get_settings
from ..security import create_access_token, COOKIE_NAME, COOKIE_SECURE, COOKIE_SAMESITE
from ..db import UserSubscription, TIER_CONFIG, UserUsage
from datetime import datetime
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

class LoginBody(BaseModel):
    username: str
    password: str

@router.post("/token")
def issue_token(body: dict):
    username = body.get("username","")
    password = body.get("password","")
    ok_user = hmac.compare_digest(username, settings.admin_user)
    ok_pass = settings.admin_password and hmac.compare_digest(password, settings.admin_password)
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(sub=username)
    return {"access_token": token, "token_type": "bearer", "expires_in": settings.jwt_expires_minutes * 60}

# New: login for browsers — sets HttpOnly cookie then redirects
@router.post("/web-login")
def web_login(username: str = Form(...), password: str = Form(...), next_path: str = Form("/upload-test")):
    ok_user = hmac.compare_digest(username, settings.admin_user)
    ok_pass = settings.admin_password and hmac.compare_digest(password, settings.admin_password)
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(sub=username)
    resp = RedirectResponse(url=next_path, status_code=303)
    resp.set_cookie(
        key=COOKIE_NAME, value=token,
        httponly=True, secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE.capitalize(),
        max_age=settings.jwt_expires_minutes * 60, path="/"
    )
    return resp

@router.post("/logout")
def logout(next_path: str = Form("/upload-test")):
    resp = RedirectResponse(url=next_path, status_code=303)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp

@router.get("/users/{user_id}/info")
async def get_user_info(user_id: str, session: Session = Depends()):
    """Get user's subscription and usage info"""
    
    # Get active subscription
    stmt = select(UserSubscription).where(
        UserSubscription.user_id == user_id,
        UserSubscription.is_active == True
    ).order_by(UserSubscription.created_at.desc())
    
    subscription = session.exec(stmt).first()
    
    tier = subscription.tier if subscription else "free"
    tier_config = TIER_CONFIG[tier]
    
    # Get current month usage
    now = datetime.utcnow()
    usage_stmt = select(UserUsage).where(
        UserUsage.user_id == user_id,
        UserUsage.year == now.year,
        UserUsage.month == now.month
    )
    usage = session.exec(usage_stmt).first()
    
    meetings_used = usage.meetings_used if usage else 0
    meetings_limit = tier_config["meetings_per_month"]
    
    return {
        "user_id": user_id,
        "email": subscription.email if subscription else None,
        "tier": tier,
        "tier_name": tier_config["name"],
        "max_file_size_mb": tier_config["max_file_size_mb"],
        "meetings_used": meetings_used,
        "meetings_limit": meetings_limit,
        "has_quota": meetings_used < meetings_limit,
       
        "subscription_expires_at": subscription.expires_at.isoformat() if subscription else None
    }
    @router.post("/users/{user_id}/usage/increment")
    async def increment_usage(user_id: str, session: Session = Depends()):
        """Increment monthly usage when user creates a meeting"""
        
        now = datetime.utcnow()
        
        # Get or create usage record
        stmt = select(UserUsage).where(
            UserUsage.user_id == user_id,
            UserUsage.year == now.year,
            UserUsage.month == now.month
        )
        usage = session.exec(stmt).first()
        
        if not usage:
            usage = UserUsage(
                user_id=user_id,
                year=now.year,
                month=now.month,
                meetings_used=1
            )
        else:
            usage.meetings_used += 1
        
        session.add(usage)
        session.commit()
        
        return {
            "success": True,
            "meetings_used": usage.meetings_used
        }