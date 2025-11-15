# app/routers/auth.py
from fastapi import APIRouter, HTTPException, Form, Depends, Response, Request
from pydantic import BaseModel
from fastapi.responses import RedirectResponse, JSONResponse
from sqlmodel import Session, select
from passlib.context import CryptContext
import hmac, os
from ..config import get_settings
from ..security import create_access_token, COOKIE_NAME, COOKIE_SECURE, COOKIE_SAMESITE
from ..portal_db import get_db_session, User

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginBody(BaseModel):
    username: str
    password: str

class RegisterBody(BaseModel):
    name: str
    email: str
    password: str

# Admin token endpoint (existing)
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

# Admin web login (existing)
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

# Client portal login
@router.post("/login")
def client_login(email: str, password: str, db: Session = Depends(get_db_session)):
    """Client portal login - returns user info with is_admin flag"""
    user = db.exec(select(User).where(User.email == email)).first()
    
    if not user or not pwd_context.verify(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Create session cookie
    token = create_access_token(sub=user.email)
    
    return JSONResponse(
        content={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_admin": user.is_admin
        },
        headers={
            "Set-Cookie": f"{COOKIE_NAME}={token}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age={settings.jwt_expires_minutes * 60}"
        }
    )

# Client portal registration
@router.post("/register")
def client_register(body: RegisterBody, db: Session = Depends(get_db_session)):
    """Register new client portal user"""
    # Check if user exists
    existing = db.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_password = pwd_context.hash(body.password)
    new_user = User(
        email=body.email,
        name=body.name,
        hashed_password=hashed_password,
        is_admin=False
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create session cookie
    token = create_access_token(sub=new_user.email)
    
    return JSONResponse(
        content={
            "id": new_user.id,
            "email": new_user.email,
            "name": new_user.name,
            "is_admin": new_user.is_admin
        },
        headers={
            "Set-Cookie": f"{COOKIE_NAME}={token}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age={settings.jwt_expires_minutes * 60}"
        }
    )

# Get current user info
@router.get("/me")
def get_current_user(request: Request, db: Session = Depends(get_db_session)):
    """Get current logged-in user"""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Decode token and get user email
    # (You'll need to implement verify_token in your security module)
    from ..security import verify_token
    payload = verify_token(token)
    email = payload.get("sub")
    
    user = db.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_admin": user.is_admin
    }

@router.post("/logout")
def logout(next_path: str = Form("/upload-test")):
    resp = RedirectResponse(url=next_path, status_code=303)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp