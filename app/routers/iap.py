# app/routers/iap.py - COMPLETE FILE WITH GOOGLE PLAY VERIFICATION

import os
import json
import secrets
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..db import get_session
from ..models import License

router = APIRouter(prefix="/iap", tags=["iap"])


class IAPVerifyRequest(BaseModel):
    receipt: str
    store: str  # 'google_play' or 'app_store'
    product_id: str
    user_id: Optional[str] = None
    email: Optional[str] = None


def verify_google_play_receipt(receipt_token: str, product_id: str) -> dict:
    """
    Verify Google Play purchase receipt with Google's servers
    """
    try:
        # Load service account credentials from environment variable
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        
        if not service_account_json:
            raise Exception("GOOGLE_SERVICE_ACCOUNT_JSON environment variable not set")
        
        print("📱 Loading Google service account from environment")
        
        # Parse JSON and create credentials
        credentials_dict = json.loads(service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=['https://www.googleapis.com/auth/androidpublisher']
        )
        
        # Build the API client
        service = build('androidpublisher', 'v3', credentials=credentials)
        print("✅ Google Play API client initialized")
        
        # Your package name from Google Play Console
        package_name = "com.fourdgaming.clipnote"
        
        print(f"🔍 Verifying subscription: {product_id}")
        print(f"📝 Token: {receipt_token[:20]}...")
        
        # Verify subscription with Google
        result = service.purchases().subscriptions().get(
            packageName=package_name,
            subscriptionId=product_id,
            token=receipt_token
        ).execute()
        
        print(f"✅ Google Play verification successful!")
        print(f"   Order ID: {result.get('orderId')}")
        print(f"   Payment State: {result.get('paymentState')}")
        print(f"   Auto-Renewing: {result.get('autoRenewing')}")
        
        # Check expiry
        expiry_ms = int(result.get('expiryTimeMillis', 0))
        expiry_date = datetime.fromtimestamp(expiry_ms / 1000) if expiry_ms else None
        
        if expiry_date:
            is_active = expiry_date > datetime.utcnow()
            print(f"   Expires: {expiry_date}")
            print(f"   Active: {is_active}")
        
        # Acknowledge the purchase (required by Google within 3 days)
        try:
            service.purchases().subscriptions().acknowledge(
                packageName=package_name,
                subscriptionId=product_id,
                token=receipt_token,
                body={}
            ).execute()
            print("✅ Subscription acknowledged")
        except HttpError as e:
            if e.resp.status == 400:
                print("ℹ️ Subscription already acknowledged")
            else:
                print(f"⚠️ Acknowledgment warning: {e}")
        
        return result
        
    except HttpError as e:
        error_content = json.loads(e.content.decode('utf-8'))
        error_msg = error_content.get('error', {}).get('message', str(e))
        print(f"❌ Google Play API error: {error_msg}")
        
        if e.resp.status == 410:
            raise Exception("Subscription has been canceled or refunded")
        elif e.resp.status == 404:
            raise Exception("Purchase not found - may not exist or is a sandbox purchase")
        else:
            raise Exception(f"Google Play verification failed: {error_msg}")
    
    except Exception as e:
        print(f"❌ Verification error: {e}")
        raise Exception(f"Receipt verification failed: {str(e)}")


@router.post("/verify")
async def verify_iap_purchase(
    request: IAPVerifyRequest,
    db: Session = Depends(get_session)
):
    """
    Verify IAP purchase and issue/update license
    """
    print(f"\n{'='*60}")
    print(f"🔐 IAP VERIFICATION REQUEST")
    print(f"{'='*60}")
    print(f"Store: {request.store}")
    print(f"Product ID: {request.product_id}")
    print(f"User ID: {request.user_id}")
    print(f"Receipt length: {len(request.receipt)} bytes")
    
    try:
        # Step 1: Verify with store
        if request.store == 'google_play':
            print(f"\n📱 Verifying with Google Play...")
            
            # Call the verification function
            verification_result = verify_google_play_receipt(
                receipt_token=request.receipt,
                product_id=request.product_id
            )
            
            # Check payment state (1 = payment received)
            payment_state = verification_result.get('paymentState')
            if payment_state != 1:
                raise HTTPException(
                    status_code=400,
                    detail="Payment not confirmed by Google Play"
                )
            
            order_id = verification_result.get('orderId')
            print(f"✅ Verified! Order ID: {order_id}")
            
        elif request.store == 'app_store':
            raise HTTPException(
                status_code=400,
                detail="App Store verification not yet implemented"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid store: {request.store}"
            )
        
        # Step 2: Map product ID to tier
        tier_mapping = {
            'com.clipnote.starter.monthly': 'starter',
            'clipnote_pro_monthly': 'pro',
            'clipnote_business_monthly': 'business',
        }
        
        tier = tier_mapping.get(request.product_id, 'free')
        print(f"📊 Mapped to tier: {tier}")
        
        # Step 3: Find or create license
        license_key = None
        
        # Try to find existing license by user_id
        if request.user_id:
            existing = db.exec(
                select(License).where(License.device_id == request.user_id)
            ).first()
            if existing:
                license_key = existing.license_key
                print(f"📝 Found existing license for user")
        
        # Try to find by email if provided
        if not license_key and request.email:
            existing = db.exec(
                select(License).where(License.email == request.email)
            ).first()
            if existing:
                license_key = existing.license_key
                print(f"📝 Found existing license for email")
        
        # Generate new license key if none found
        if not license_key:
            license_key = f"lic_{secrets.token_urlsafe(32)}"
            print(f"🆕 Generated new license key")
        
        # Step 4: Update or create license in database
        license_obj = db.exec(
            select(License).where(License.license_key == license_key)
        ).first()
        
        if license_obj:
            print(f"📝 Updating existing license to tier: {tier}")
            license_obj.tier = tier
            license_obj.device_id = request.user_id
            if request.email:
                license_obj.email = request.email
            license_obj.iap_purchase_token = request.receipt
            license_obj.iap_product_id = request.product_id
            license_obj.iap_store = request.store
        else:
            print(f"🆕 Creating new license with tier: {tier}")
            license_obj = License(
                license_key=license_key,
                tier=tier,
                device_id=request.user_id,
                email=request.email,
                iap_purchase_token=request.purchase_token,
                iap_product_id=request.product_id,
                iap_store=request.store,
            )
            db.add(license_obj)
        
        db.commit()
        db.refresh(license_obj)
        
        print(f"\n{'='*60}")
        print(f"✅ IAP VERIFICATION COMPLETE")
        print(f"{'='*60}")
        print(f"License Key: {license_key[:20]}...")
        print(f"Tier: {tier}")
        print(f"User ID: {request.user_id}")
        print(f"{'='*60}\n")
        
        return {
            "license_key": license_key,
            "tier": tier,
            "message": "Purchase verified successfully"
        }
        
    except HTTPException:
        raise
    
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ IAP VERIFICATION FAILED")
        print(f"{'='*60}")
        print(f"Error: {str(e)}")
        print(f"{'='*60}\n")
        
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )