import requests
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from app.portal_db import UserSubscription

router = APIRouter(prefix="/apple", tags=["apple"])

@router.post("/iap/verify/apple")
async def verify_app_store(request: dict, session: Session = Depends()):
    """
    Verify App Store purchase
    
    Request:
    {
      "user_id": "device_id_or_user_id",
      "receipt_data": "base64_receipt",
      "product_id": "clipnote_pro_monthly"
    }
    """
    user_id = request["user_id"]
    receipt_data = request["receipt_data"]
    product_id = request["product_id"]
    
    # Apple verification endpoint (use sandbox for testing)
    url = "https://buy.itunes.apple.com/verifyReceipt"
    # For production: https://buy.itunes.apple.com/verifyReceipt
    # For sandbox: https://sandbox.itunes.apple.com/verifyReceipt
    
    payload = {
        "receipt-data": receipt_data,
        "password": os.getenv("APPLE_SHARED_SECRET"),  # From App Store Connect
        "exclude-old-transactions": True
    }
    
    response = requests.post(url, json=payload)
    result = response.json()
    
    if result.get("status") != 0:
        # Try sandbox if production fails
        url = "https://sandbox.itunes.apple.com/verifyReceipt"
        response = requests.post(url, json=payload)
        result = response.json()
    
    if result.get("status") == 0:
        # Find the subscription in latest_receipt_info
        latest_info = result.get("latest_receipt_info", [])
        
        for item in latest_info:
            if item["product_id"] == product_id:
                expiry_ms = int(item["expires_date_ms"])
                expiry_date = datetime.fromtimestamp(expiry_ms / 1000)
                is_active = expiry_date > datetime.utcnow()
                
                tier = "professional" if "pro" in product_id else "business"
                transaction_id = item["transaction_id"]
                
                # Create or update subscription
                stmt = select(UserSubscription).where(
                    UserSubscription.purchase_token == transaction_id
                )
                sub = session.exec(stmt).first()
                
                if not sub:
                    sub = UserSubscription(
                        user_id=user_id,
                        tier=tier,
                        store="app_store",
                        product_id=product_id,
                        purchase_token=transaction_id,
                        original_transaction_id=item.get("original_transaction_id"),
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
        
        raise HTTPException(400, "Product not found in receipt")
    else:
        raise HTTPException(400, f"Receipt validation failed: {result.get('status')}")