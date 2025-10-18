# app/routers/iap.py
"""
Bridge IAP purchases to existing license system
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build

from ..db import get_session
from ..models import License, LicenseTier
from ..services.license import create_license, get_license_info

router = APIRouter(prefix="/iap", tags=["In-App Purchases"])


class IAPVerifyRequest(BaseModel):
    user_id: str  # Device ID or user identifier
    email: Optional[str] = None
    receipt: str  # Purchase token (Android) or receipt data (iOS)
    product_id: str  # com.clipnote.pro.monthly or com.clipnote.business.monthly
    store: str  # "google_play" or "app_store"


class IAPVerifyResponse(BaseModel):
    success: bool
    license_key: str
    tier: str
    tier_name: str
    expires_at: Optional[str] = None
    message: str


@router.post("/verify", response_model=IAPVerifyResponse)
async def verify_iap_receipt(
    request: IAPVerifyRequest,
    db: Session = Depends(get_session)
):
    """
    Verify IAP receipt and create/update license
    
    Flow:
    1. Verify receipt with Google Play or App Store
    2. Determine tier from product_id
    3. Create or update license in database
    4. Return license key for app to use
    """
    
    # Determine tier from product_id
    if "pro" in request.product_id.lower():
        tier = LicenseTier.PROFESSIONAL
    elif "business" in request.product_id.lower():
        tier = LicenseTier.BUSINESS
    else:
        raise HTTPException(400, "Invalid product_id")
    
    # Verify receipt based on store
    if request.store == "google_play":
        verification_result = await _verify_google_play(
            request.receipt,
            request.product_id
        )
    elif request.store == "app_store":
        verification_result = await _verify_app_store(
            request.receipt,
            request.product_id
        )
    else:
        raise HTTPException(400, "Invalid store. Must be 'google_play' or 'app_store'")
    
    if not verification_result["valid"]:
        raise HTTPException(400, f"Receipt verification failed: {verification_result['error']}")
    
    # Check if license already exists for this user/purchase
    stmt = select(License).where(
        License.email == request.email,
        License.tier == tier.value
    ).order_by(License.created_at.desc())
    
    existing_license = db.exec(stmt).first()
    
    if existing_license and existing_license.is_active:
        # Update existing license
        existing_license.expires_at = verification_result.get("expires_at")
        existing_license.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing_license)
        license = existing_license
    else:
        # Create new license
        license = create_license(
            session=db,
            email=request.email or f"{request.user_id}@app.clipnote.ai",
            tier=tier,
            iap_purchase_token=request.receipt
        )
        license.expires_at = verification_result.get("expires_at")
        db.commit()
        db.refresh(license)
    
    # Get full license info
    license_info = get_license_info(db, license.license_key)
    
    return IAPVerifyResponse(
        success=True,
        license_key=license.license_key,
        tier=license.tier,
        tier_name=license_info["tier_name"],
        expires_at=license.expires_at.isoformat() if license.expires_at else None,
        message=f"Subscription verified: {license_info['tier_name']}"
    )


async def _verify_google_play(purchase_token: str, product_id: str) -> dict:
    """Verify Google Play subscription"""
    try:
        # Load service account credentials
        creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not creds_path:
            return {"valid": False, "error": "Google service account not configured"}
        
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/androidpublisher"]
        )
        
        # Build API client
        service = build('androidpublisher', 'v3', credentials=credentials)
        
        # Verify subscription
        result = service.purchases().subscriptions().get(
            packageName=os.getenv("ANDROID_PACKAGE_NAME", "com.clipnote"),
            subscriptionId=product_id,
            token=purchase_token
        ).execute()
        
        # Check if subscription is active
        expiry_ms = int(result.get('expiryTimeMillis', 0))
        expiry_date = datetime.fromtimestamp(expiry_ms / 1000) if expiry_ms else None
        is_active = expiry_date > datetime.utcnow() if expiry_date else False
        
        return {
            "valid": is_active,
            "expires_at": expiry_date,
            "error": None if is_active else "Subscription expired"
        }
        
    except Exception as e:
        return {"valid": False, "error": str(e)}


async def _verify_app_store(receipt_data: str, product_id: str) -> dict:
    """Verify App Store subscription"""
    try:
        # Apple verification endpoint
        # Try production first, fall back to sandbox
        url = "https://buy.itunes.apple.com/verifyReceipt"
        
        payload = {
            "receipt-data": receipt_data,
            "password": os.getenv("APPLE_SHARED_SECRET"),
            "exclude-old-transactions": True
        }
        
        response = requests.post(url, json=payload, timeout=30)
        result = response.json()
        
        # If production fails with 21007, try sandbox
        if result.get("status") == 21007:
            url = "https://sandbox.itunes.apple.com/verifyReceipt"
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
        
        if result.get("status") == 0:
            # Find the subscription
            latest_info = result.get("latest_receipt_info", [])
            
            for item in latest_info:
                if item["product_id"] == product_id:
                    expiry_ms = int(item["expires_date_ms"])
                    expiry_date = datetime.fromtimestamp(expiry_ms / 1000)
                    is_active = expiry_date > datetime.utcnow()
                    
                    return {
                        "valid": is_active,
                        "expires_at": expiry_date,
                        "error": None if is_active else "Subscription expired"
                    }
            
            return {"valid": False, "error": "Product not found in receipt"}
        else:
            return {"valid": False, "error": f"Apple verification failed: {result.get('status')}"}
            
    except Exception as e:
        return {"valid": False, "error": str(e)}


@router.get("/subscription-status/{license_key}")
async def get_subscription_status(
    license_key: str,
    db: Session = Depends(get_session)
):
    """Get subscription status for a license"""
    
    license_info = get_license_info(db, license_key)
    
    if not license_info["valid"]:
        raise HTTPException(404, "License not found")
    
    return {
        "license_key": license_key,
        "tier": license_info["tier"],
        "tier_name": license_info["tier_name"],
        "is_active": license_info["is_active"],
        "expires_at": license_info.get("expires_at"),
        "meetings_used": license_info["meetings_used"],
        "meetings_limit": license_info["meetings_limit"],
        "has_quota": license_info["has_quota"]
    }