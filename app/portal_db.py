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

class Subscription(SQLModel, table=True):
    """Subscription model for recurring maintenance plans"""
    __tablename__ = "subscriptions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="portaluser.id", index=True)
    project_id: Optional[int] = Field(default=None, foreign_key="project.id", index=True)
    
    stripe_subscription_id: str = Field(unique=True, index=True)
    stripe_customer_id: str = Field(index=True)
    stripe_price_id: str
    
    plan_id: str
    plan_name: str
    amount: float
    currency: str = Field(default="usd")
    interval: str = Field(default="month")
    
    status: str = Field(default="active")
    cancel_at_period_end: bool = Field(default=False)
    
    start_date: datetime
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    last_payment_date: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    meta_data: Optional[str] = None
    
# ---------- SESSION HELPERS ----------

def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)
    
# Add Review model to portal_db.py
class Review(SQLModel, table=True):
    """Client reviews for 4D Gaming services"""
    __tablename__ = "reviews"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="portaluser.id")
    rating: int = Field(ge=1, le=5)  # 1-5 stars
    comment: str
    is_approved: bool = Field(default=False)  # Admin must approve before showing publicly
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Add PasswordReset model to portal_db.py
class PasswordReset(SQLModel, table=True):
    """Password reset tokens"""
    __tablename__ = "password_resets"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)