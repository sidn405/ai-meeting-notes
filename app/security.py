# app/security.py
from datetime import datetime, timedelta, timezone
import hmac, os
from typing import Optional
import jwt  # PyJWT
from fastapi import HTTPException, Depends, Header, Cookie
from fastapi.security.utils import get_authorization_scheme_param
from .config import get_settings

settings = get_settings()

COOKIE_NAME = os.getenv("COOKIE_NAME", "access_token")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1") == "1"    # set to 1 in prod (HTTPS); 0 for localhost
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")     # lax/strict/none

def _now() -> datetime:
    return datetime.now(timezone.utc)

def create_access_token(sub: str, expires_minutes: Optional[int] = None) -> str:
    exp_mins = expires_minutes or settings.jwt_expires_minutes
    payload = {
        "sub": sub,
        "iat": int(_now().timestamp()),
        "exp": int((_now() + timedelta(minutes=exp_mins)).timestamp()),
        "iss": "ai-meeting-notes",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)

def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def _const_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())

async def require_auth(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    access_token_cookie: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
):
    # 1) API key
    if api_key:
        for key in settings.api_keys:
            if _const_time_eq(api_key, key):
                return {"auth": "api_key", "sub": "api_key_user"}

        raise HTTPException(status_code=401, detail="Invalid API key")

    # 2) Bearer header
    if authorization:
        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() == "bearer" and token:
            payload = _decode_token(token)
            return {"auth": "jwt", "sub": payload.get("sub", "unknown")}

    # 3) Cookie (for browser forms)
    if access_token_cookie:
        payload = _decode_token(access_token_cookie)
        return {"auth": "cookie", "sub": payload.get("sub", "unknown")}

    # 4) Dev bypass (never enable in prod)
    if settings.dev_allow_no_auth:
        return {"auth": "dev", "sub": "dev-user"}

    raise HTTPException(status_code=401, detail="Unauthorized.")
