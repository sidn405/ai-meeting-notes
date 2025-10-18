# app/routers/auth.py
from fastapi import APIRouter, HTTPException, Form, Depends
from pydantic import BaseModel
from fastapi.responses import RedirectResponse, JSONResponse
import hmac, os
from ..config import get_settings
from ..security import create_access_token, COOKIE_NAME, COOKIE_SECURE, COOKIE_SAMESITE
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
