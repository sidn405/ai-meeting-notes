"""
License API Router for SQLModel
Add this as routers/license.py
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Cookie
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr
from typing import Optional
import os
from datetime import datetime
from ..db import get_session
from ..services.license import (
    create_license,
    validate_license,
    get_license_info,
    deactivate_license,
    LicenseTier
)
from ..models import License

router = APIRouter(prefix="/license", tags=["license"])

# Admin API key for generating licenses
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "change-me-in-production")

class CreateLicenseRequest(BaseModel):
    email: EmailStr
    tier: str  # "starter", "professional", or "business"
    gumroad_order_id: Optional[str] = None

class ActivateLicenseRequest(BaseModel):
    license_key: str

class LicenseInfoResponse(BaseModel):
    valid: bool
    license_key: Optional[str] = None
    email: Optional[str] = None
    tier: Optional[str] = None
    tier_name: Optional[str] = None
    max_file_size_mb: Optional[int] = None
    meetings_used: Optional[int] = None
    meetings_limit: Optional[int] = None
    has_quota: Optional[bool] = None
    activated_at: Optional[str] = None
    is_active: Optional[bool] = None
    error: Optional[str] = None

def verify_admin(x_api_key: Optional[str] = Header(None)):
    """Verify admin API key"""
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("/generate")
def generate_license(
    request: CreateLicenseRequest,
    session: Session = Depends(get_session),
    _admin: None = Depends(verify_admin)
):
    """
    Admin endpoint: Generate a new license
    Requires X-API-Key header
    """
    try:
        tier = LicenseTier(request.tier.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier. Must be: starter, professional, or business"
        )
    
    license = create_license(
        session=session,
        email=request.email,
        tier=tier,
        gumroad_order_id=request.gumroad_order_id
    )
    
    return {
        "success": True,
        "license_key": license.license_key,
        "email": license.email,
        "tier": license.tier,
        "message": "License created successfully"
    }

@router.post("/activate")
def activate_license(
    request: ActivateLicenseRequest,
    session: Session = Depends(get_session)
):
    """
    User endpoint: Validate and activate a license key
    Sets a cookie with the license key
    """
    is_valid, license, error = validate_license(session, request.license_key)
    
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    
    info = get_license_info(session, request.license_key)
    
    response = JSONResponse(content={
        "success": True,
        "message": "License activated successfully",
        **info
    })
    
    # Set license key cookie (30 days)
    response.set_cookie(
        key="license_key",
        value=request.license_key,
        max_age=60*60*24*30,  # 30 days
        httponly=True,
        samesite="lax"
    )
    
    return response

@router.get("/info", response_model=LicenseInfoResponse)
def get_info(
    license_key: Optional[str] = Cookie(None),
    session: Session = Depends(get_session)
):
    """Get current license information from cookie"""
    if not license_key:
        return LicenseInfoResponse(
            valid=False,
            error="No license key provided"
        )
    
    info = get_license_info(session, license_key)
    return LicenseInfoResponse(**info)

@router.post("/deactivate")
def deactivate(
    license_key: str,
    session: Session = Depends(get_session),
    _admin: None = Depends(verify_admin)
):
    """
    Admin endpoint: Deactivate a license
    Requires X-API-Key header
    """
    success = deactivate_license(session, license_key)
    
    if not success:
        raise HTTPException(status_code=404, detail="License not found")
    
    return {
        "success": True,
        "message": "License deactivated"
    }

@router.get("/validate/{license_key}")
def validate_key(
    license_key: str,
    session: Session = Depends(get_session)
):
    """Public endpoint: Validate a license key (no auth required)"""
    is_valid, license, error = validate_license(session, license_key)
    
    if not is_valid:
        return {
            "valid": False,
            "error": error
        }
    
    return {
        "valid": True,
        "tier": license.tier,
        "email": license.email
    }

@router.get("/list")
def list_licenses(
    session: Session = Depends(get_session),
    _admin: None = Depends(verify_admin)
):
    """
    Admin endpoint: List all licenses
    Requires X-API-Key header
    """
    statement = select(License).order_by(License.created_at.desc())
    licenses = session.exec(statement).all()
    
    return [
        {
            "license_key": lic.license_key,
            "email": lic.email,
            "tier": lic.tier,
            "is_active": lic.is_active,
            "activated_at": lic.activated_at.isoformat() if lic.activated_at else None,
            "created_at": lic.created_at.isoformat() if lic.created_at else None,
            "gumroad_order_id": lic.gumroad_order_id
        }
        for lic in licenses
    ]