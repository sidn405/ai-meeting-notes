# app/db.py
import os
from sqlmodel import SQLModel, create_engine, Session
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

def _pg_url(url: str) -> str:
    # Allow postgres:// and upgrade to psycopg driver
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

if DATABASE_URL:
    engine = create_engine(_pg_url(DATABASE_URL), pool_pre_ping=True)
else:
    DB_PATH = DATA_DIR / "app.db"
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

def init_db():
    from .models import Meeting
    SQLModel.metadata.create_all(engine)

def get_session():
    return Session(engine)
