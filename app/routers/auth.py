# app/routers/auth.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import hmac
from ..config import get_settings
from ..security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

class LoginBody(BaseModel):
    username: str
    password: str

@router.post("/token")
def issue_token(body: LoginBody):
    # simple constant-time check against env creds
    ok_user = hmac.compare_digest(body.username, settings.admin_user)
    ok_pass = settings.admin_password and hmac.compare_digest(body.password, settings.admin_password)
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(sub=body.username)
    return {"access_token": token, "token_type": "bearer", "expires_in": settings.jwt_expires_minutes * 60}
