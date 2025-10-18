# app/db.py
import os
from sqlmodel import SQLModel, create_engine, Session, Field
from datetime import datetime
from typing import Optional
from .models import License, LicenseUsage
from sqlalchemy import text
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "app.db"

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
ALLOW_SQLITE_FALLBACK = os.getenv("DB_ALLOW_SQLITE_FALLBACK", "0") == "1"

class UserSubscription(SQLModel, table=True):
    __tablename__ = "user_subscriptions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)  # Device ID or auth user ID
    email: Optional[str] = Field(default=None)
    
    # Subscription details
    tier: str = Field(default="free")  # free, professional, business
    store: str  # google_play or app_store
    product_id: str  # com.clipnote.pro.monthly
    
    # Purchase info
    purchase_token: str = Field(unique=True)  # Google: purchase token, Apple: transaction ID
    original_transaction_id: Optional[str] = None  # Apple only
    
    # Status
    is_active: bool = Field(default=True)
    expires_at: Optional[datetime] = None
    
    # Tracking
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_verified_at: Optional[datetime] = None


class UserUsage(SQLModel, table=True):
    __tablename__ = "user_usage"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    year: int
    month: int
    meetings_used: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
TIER_CONFIG = {
    "free": {
        "name": "Free",
        "meetings_per_month": 5,
        "max_file_size_mb": 50,
    },
    "professional": {
        "name": "Professional",
        "meetings_per_month": 50,
        "max_file_size_mb": 200,
    },
    "business": {
        "name": "Business",
        "meetings_per_month": 100,
        "max_file_size_mb": 500,
    }
}

def _pg_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

def _try_pg_engine():
    if not DATABASE_URL:
        return None
    try:
        eng = create_engine(_pg_url(DATABASE_URL), pool_pre_ping=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except Exception as e:
        print(f"[DB] Postgres connect failed: {e!r}")
        if not ALLOW_SQLITE_FALLBACK:
            raise
        return None

_engine = _try_pg_engine() or create_engine(f"sqlite:///{DB_PATH}", echo=False)



# ========== NEW: Database-agnostic column checking ==========
def ensure_meeting_progress_columns():
    """Add progress and step columns if they don't exist"""
    with _engine.connect() as conn:
        dialect_name = conn.dialect.name
        
        if dialect_name == "postgresql":
            result = conn.exec_driver_sql(
                "SELECT column_name FROM information_schema.columns WHERE table_name='meeting';"
            )
            cols = {r[0] for r in result}
            
            if "progress" not in cols:
                conn.exec_driver_sql("ALTER TABLE meeting ADD COLUMN progress INTEGER DEFAULT 0;")
                conn.commit()
            if "step" not in cols:
                conn.exec_driver_sql("ALTER TABLE meeting ADD COLUMN step TEXT;")
                conn.commit()
                
        elif dialect_name == "sqlite":
            result = conn.exec_driver_sql("PRAGMA table_info(meeting);")
            cols = {r[1] for r in result}
            
            if "progress" not in cols:
                conn.exec_driver_sql("ALTER TABLE meeting ADD COLUMN progress INTEGER DEFAULT 0;")
                conn.commit()
            if "step" not in cols:
                conn.exec_driver_sql("ALTER TABLE meeting ADD COLUMN step TEXT;")
                conn.commit()
# ========== END NEW ==========

def init_db():
    SQLModel.metadata.create_all(_engine)
    ensure_meeting_progress_columns()

def get_session():
    return Session(_engine)