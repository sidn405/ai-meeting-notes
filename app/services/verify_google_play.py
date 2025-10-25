from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from db import UserSubscription

router = APIRouter(prefix="/google", tags=["google"])

@router.post("/iap/verify/google")
async def verify_google_play(request: dict, session: Session = Depends()):
    """
    Verify Google Play purchase (subscription or product)
    """
    user_id = request["user_id"]
    purchase_token = request["purchase_token"]
    product_id = request["product_id"]

    credentials = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/androidpublisher"],
    )

    service = build("androidpublisher", "v3", credentials=credentials, cache_discovery=False)

    pkg = os.getenv("ANDROID_PACKAGE_NAME")  # e.g. com.fourdgaming.clipnote
    tier = "professional" if "pro" in product_id else "business"

    try:
        # -- Prefer subscriptionsv2 endpoint --
        result = service.purchases().subscriptionsv2().get(
            packageName=pkg,
            token=purchase_token
        ).execute()

        state = result.get("subscriptionState", "UNKNOWN")
        expiry_ms = 0
        if result.get("lineItems"):
            expiry_ms = int(result["lineItems"][0]["expiryTime"][:-3])  # convert seconds->ms if needed
        expiry_date = datetime.fromtimestamp(expiry_ms / 1000) if expiry_ms else None
        is_active = state == "SUBSCRIPTION_STATE_ACTIVE"

    except HttpError as e:
        # handle legacy / product path fallback
        if e.resp.status == 404 or "subscriptionsv2" in str(e):
            try:
                result = service.purchases().products().get(
                    packageName=pkg,
                    productId=product_id,
                    token=purchase_token
                ).execute()
                is_active = result.get("purchaseState") == 0
                expiry_date = datetime.utcnow()
            except HttpError as inner:
                raise HTTPException(status_code=400, detail=f"Play API error: {inner}")
        else:
            raise HTTPException(status_code=400, detail=f"Play API error: {e}")

    # -- Save subscription --
    stmt = select(UserSubscription).where(UserSubscription.purchase_token == purchase_token)
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
            last_verified_at=datetime.utcnow(),
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
        "expires_at": expiry_date.isoformat() if expiry_date else None,
    }
