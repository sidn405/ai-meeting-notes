from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()

# === License System Models ===

# License Tier Enum
class LicenseTier(str, enum.Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    BUSINESS = "business"

# License Model
class License(SQLModel, table=True):
    __tablename__ = "licenses"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    license_key: str = Field(unique=True, index=True)
    tier: str  # Will store LicenseTier enum values
    email: str
    
    # Status
    is_active: bool = Field(default=True)
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # Gumroad integration
    gumroad_order_id: Optional[str] = Field(default=None, unique=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

# License Usage Model
class LicenseUsage(SQLModel, table=True):
    __tablename__ = "license_usage"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    license_key: str = Field(index=True)
    
    # Monthly usage tracking
    year: int
    month: int
    meetings_used: int = Field(default=0)

# Tier Limits Configuration
TIER_LIMITS = {
    LicenseTier.STARTER: {
        "max_file_size_mb": 50,
        "meetings_per_month": 10,
        "price": 29,
        "name": "Starter",
        "description": "Perfect for occasional meetings"
    },
    LicenseTier.PROFESSIONAL: {
        "max_file_size_mb": 200,
        "meetings_per_month": 50,
        "price": 79,
        "name": "Professional",
        "description": "For regular users and consultants"
    },
    LicenseTier.BUSINESS: {
        "max_file_size_mb": 500,
        "meetings_per_month": 999999,  # Effectively unlimited
        "price": 149,
        "name": "Business",
        "description": "Unlimited meetings for teams"
    }
}

class Meeting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    audio_path: Optional[str] = None
    transcript_path: Optional[str] = None
    summary_path: Optional[str] = None
    status: str = "uploaded"  # uploaded|transcribed|summarized|delivered
    created_at: datetime = Field(default_factory=datetime.utcnow)
    email_to: Optional[str] = None
    slack_channel: Optional[str] = None
    status: str = "queued"
    # NEW:
    progress: int = 0
    step: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)