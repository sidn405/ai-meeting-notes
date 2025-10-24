# app/routers/iap.py
"""
Bridge IAP purchases to existing license system
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from starlette.background import BackgroundTask
from fastapi.responses import JSONResponse
from ..db import get_session
from ..models import License, LicenseTier
from ..services.license import create_license, get_license_info

router = APIRouter(prefix="/iap", tags=["In-App Purchases"])



class IAPVerifyRequest(BaseModel):
    user_id: str
    email: Optional[str] = None
    receipt: str
    product_id: str
    store: str

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
    
    print(f"\n{'='*60}")
    print(f"🔐 IAP VERIFICATION START")
    print(f"{'='*60}")
    print(f"User ID: {request.user_id}")
    print(f"Store: {request.store}")
    print(f"Product ID: {request.product_id}")
    print(f"Email: {request.email}")
    
    # Determine tier from product_id
    if "starter" in request.product_id.lower():
        tier = LicenseTier.STARTER
    elif "pro" in request.product_id.lower() or "professional" in request.product_id.lower():
        tier = LicenseTier.PROFESSIONAL
    elif "business" in request.product_id.lower():
        tier = LicenseTier.BUSINESS
    else:
        print(f"❌ Invalid product_id: {request.product_id}")
        raise HTTPException(400, "Invalid product_id")
    
    print(f"✅ Tier determined: {tier.value}")
    
    # Verify receipt based on store
    try:
        if request.store == "google_play":
            print(f"🔍 Verifying with Google Play...")
            verification_result = await _verify_google_play(
                request.receipt,
                request.product_id
            )
        elif request.store == "app_store":
            print(f"🔍 Verifying with App Store...")
            verification_result = await _verify_app_store(
                request.receipt,
                request.product_id
            )
        else:
            raise HTTPException(400, "Invalid store. Must be 'google_play' or 'app_store'")
        
        if not verification_result["valid"]:
            print(f"❌ Receipt verification failed: {verification_result['error']}")
            raise HTTPException(400, f"Receipt verification failed: {verification_result['error']}")
        
        print(f"✅ Receipt verified successfully")
        print(f"   Expires at: {verification_result.get('expires_at')}")
        
    except Exception as e:
        print(f"❌ Verification error: {e}")
        raise
    
    # Get or create license
    try:
        # Use email if provided, otherwise use user_id
        license_email = request.email or f"{request.user_id}@app.clipnote.ai"
        
        print(f"\n📋 Checking for existing license...")
        print(f"   Email: {license_email}")
        print(f"   Tier: {tier.value}")
        
        # Check if license already exists for this email/tier
        stmt = select(License).where(
            License.email == license_email,
            License.tier == tier.value
        ).order_by(License.created_at.desc())
        
        existing_license = db.exec(stmt).first()
        
        if existing_license and existing_license.is_active:
            print(f"✅ Found existing license: {existing_license.license_key}")
            print(f"   Updating expiry and IAP token...")
            
            # Update existing license
            existing_license.expires_at = verification_result.get("expires_at")
            existing_license.iap_purchase_token = request.receipt
            existing_license.updated_at = datetime.utcnow()
            db.add(existing_license)
            db.commit()
            db.refresh(existing_license)
            license = existing_license
        else:
            print(f"✅ Creating new license...")
            
            # Create new license
            license = create_license(
                session=db,
                email=license_email,
                tier=tier,
                iap_purchase_token=request.receipt
            )
            license.expires_at = verification_result.get("expires_at")
            db.add(license)
            db.commit()
            db.refresh(license)
        
        print(f"\n✅ License saved to database")
        print(f"   Key: {license.license_key[:20]}...")
        print(f"   Tier: {license.tier}")
        print(f"   Email: {license.email}")
        print(f"   Active: {license.is_active}")
        print(f"   Expires: {license.expires_at}")
        
        # Get full license info
        license_info = get_license_info(db, license.license_key)
        
        print(f"\n{'='*60}")
        print(f"🎉 IAP VERIFICATION SUCCESS")
        print(f"{'='*60}")
        print(f"License Key: {license.license_key[:20]}...")
        print(f"Tier: {license_info['tier_name']}")
        print(f"Expires: {license.expires_at}")
        
        response = IAPVerifyResponse(
            success=True,
            license_key=license.license_key,
            tier=license.tier,
            tier_name=license_info["tier_name"],
            expires_at=license.expires_at.isoformat() if license.expires_at else None,
            message=f"Subscription verified: {license_info['tier_name']}"
        )
        
        print(f"\n📤 Returning response: {response.dict()}\n")
        return response
        
    except Exception as e:
        print(f"❌ License creation/update error: {e}")
        raise HTTPException(500, f"Failed to save license: {str(e)}")


async def _verify_google_play(purchase_token: str, product_id: str) -> dict:
    """Verify Google Play subscription"""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        
        # Load service account credentials
        creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not creds_path:
            print("❌ GOOGLE_SERVICE_ACCOUNT_JSON not configured")
            return {"valid": False, "error": "Google service account not configured"}
        
        print(f"   Loading credentials from: {creds_path}")
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/androidpublisher"]
        )
        
        # Build API client
        service = build('androidpublisher', 'v3', credentials=credentials)
        
        package_name = os.getenv("ANDROID_PACKAGE_NAME", "com.fourdgaming.clipnote")
        print(f"   Package: {package_name}")
        print(f"   Product ID: {product_id}")
        print(f"   Token: {purchase_token[:20]}...")
        
        # Verify subscription
        result = service.purchases().subscriptions().get(
            packageName=package_name,
            subscriptionId=product_id,
            token=purchase_token
        ).execute()
        
        print(f"   ✅ Google Play API response: {result}")
        
        # Check if subscription is active
        expiry_ms = int(result.get('expiryTimeMillis', 0))
        expiry_date = datetime.fromtimestamp(expiry_ms / 1000) if expiry_ms else None
        is_active = expiry_date > datetime.utcnow() if expiry_date else False
        
        print(f"   Expiry: {expiry_date}")
        print(f"   Is active: {is_active}")
        
        return {
            "valid": is_active,
            "expires_at": expiry_date,
            "error": None if is_active else "Subscription expired"
        }
        
    except Exception as e:
        print(f"   ❌ Google Play verification error: {e}")
        return {"valid": False, "error": str(e)}


async def _verify_app_store(receipt_data: str, product_id: str) -> dict:
    """Verify App Store subscription"""
    try:
        import requests
        
        # Apple verification endpoint
        url = "https://buy.itunes.apple.com/verifyReceipt"
        
        payload = {
            "receipt-data": receipt_data,
            "password": os.getenv("APPLE_SHARED_SECRET"),
            "exclude-old-transactions": True
        }
        
        print(f"   Sending to: {url}")
        response = requests.post(url, json=payload, timeout=30)
        result = response.json()
        
        print(f"   Apple response status: {result.get('status')}")
        
        # If production fails with 21007, try sandbox
        if result.get("status") == 21007:
            print(f"   Trying sandbox...")
            url = "https://sandbox.itunes.apple.com/verifyReceipt"
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
        
        if result.get("status") == 0:
            # Find the subscription
            latest_info = result.get("latest_receipt_info", [])
            print(f"   Found {len(latest_info)} transactions")
            
            for item in latest_info:
                if item["product_id"] == product_id:
                    expiry_ms = int(item["expires_date_ms"])
                    expiry_date = datetime.fromtimestamp(expiry_ms / 1000)
                    is_active = expiry_date > datetime.utcnow()
                    
                    print(f"   Product found: {product_id}")
                    print(f"   Expires: {expiry_date}")
                    print(f"   Is active: {is_active}")
                    
                    return {
                        "valid": is_active,
                        "expires_at": expiry_date,
                        "error": None if is_active else "Subscription expired"
                    }
            
            print(f"   ❌ Product not found in receipt: {product_id}")
            return {"valid": False, "error": "Product not found in receipt"}
        else:
            print(f"   ❌ Apple verification failed: {result.get('status')}")
            return {"valid": False, "error": f"Apple verification failed: {result.get('status')}"}
            
    except Exception as e:
        print(f"   ❌ App Store verification error: {e}")
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