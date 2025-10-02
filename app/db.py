# app/db.py
import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "app.db"

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
ALLOW_SQLITE_FALLBACK = os.getenv("DB_ALLOW_SQLITE_FALLBACK", "0") == "1"

def _pg_url(url: str) -> str:
    # Railway gives postgres://...  Convert to SQLAlchemy's psycopg driver.
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
        # sanity check the connection so we fail at startup if broken
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except Exception as e:
        # In prod, you usually want this to hard-fail. Allow fallback only if explicitly enabled.
        print(f"[DB] Postgres connect failed: {e!r}")
        if not ALLOW_SQLITE_FALLBACK:
            raise
        return None

_engine = _try_pg_engine() or create_engine(f"sqlite:///{DB_PATH}", echo=False)

def init_db():
    from .models import Meeting
    SQLModel.metadata.create_all(_engine)

def get_session():
    return Session(_engine)
