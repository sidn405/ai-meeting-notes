from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from db import UserSubscription

router = APIRouter(prefix="/google", tags=["google"])


@router.post("/iap/verify/google")
async def verify_google_play(request: dict, session: Session = Depends()):
    """
    Verify Google Play purchase
    
    Request:
    {
      "user_id": "device_id_or_user_id",
      "purchase_token": "purchase_token_from_google",
      "product_id": "lipnote_pro_monthly"
    }
    """
    user_id = request["user_id"]
    purchase_token = request["purchase_token"]
    product_id = request["product_id"]
    
    # Load service account credentials
    credentials = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/androidpublisher"]
    )
    
    # Build the API client
    service = build('androidpublisher', 'v3', credentials=credentials)
    
    try:
        # Verify subscription
        result = service.purchases().subscriptions().get(
            packageName=os.getenv("ANDROID_PACKAGE_NAME"),  # com.clipnote
            subscriptionId=product_id,
            token=purchase_token
        ).execute()
        
        # Check if subscription is active
        expiry_ms = int(result.get('expiryTimeMillis', 0))
        expiry_date = datetime.fromtimestamp(expiry_ms / 1000)
        is_active = expiry_date > datetime.utcnow()
        
        # Determine tier
        tier = "professional" if "pro" in product_id else "business"
        
        # Create or update subscription
        stmt = select(UserSubscription).where(
            UserSubscription.purchase_token == purchase_token
        )
        sub = session.exec(stmt).first()
        
        if not sub:
            sub = UserSubscription(
                user_id=user_id,
                tier=tier,
                store="google_play",
                product_id=product_id,
                purchase_token=purchase_token,
                is_active=is_active,
                expires_at=expiry_date,
                last_verified_at=datetime.utcnow()
            )
        else:
            sub.is_active = is_active
            sub.expires_at = expiry_date
            sub.last_verified_at = datetime.utcnow()
        
        session.add(sub)
        session.commit()
        
        return {
            "success": True,
            "tier": tier,
            "is_active": is_active,
            "expires_at": expiry_date.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(400, f"Verification failed: {str(e)}")