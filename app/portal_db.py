# portal_db.py
import os
from typing import Optional
from sqlmodel import SQLModel, Field, Session, create_engine
from datetime import datetime

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://user:pass@localhost/4dgaming_client_portal",
)

engine = create_engine(DATABASE_URL, echo=False)


# ---------- MODELS (client portal only) ----------

class PortalUser(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    hashed_password: str
    is_admin: bool = Field(default=False)


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="portaluser.id")
    name: str
    service: str
    notes: Optional[str] = None
    status: str = Field(default="pending")  # pending | in-progress | completed
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectFile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    original_name: str
    s3_key: str
    url: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    sender: str  # "client" or "owner"
    body: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    
# ---------- SESSION HELPERS ----------

def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)