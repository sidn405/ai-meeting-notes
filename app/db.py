# app/db.py
import os
from sqlmodel import SQLModel, create_engine, Session
#from .models import License, LicenseUsage
from sqlalchemy import text
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "app.db"

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
ALLOW_SQLITE_FALLBACK = os.getenv("DB_ALLOW_SQLITE_FALLBACK", "0") == "1"

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
    from .models import License, LicenseUsage, Meeting  # Import here to register models
    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    ensure_meeting_progress_columns()

def get_session():
    return Session(_engine)