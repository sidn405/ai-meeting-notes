"""
License Service for SQLModel
Add this as services/license.py
"""
import secrets
from datetime import datetime
from sqlmodel import Session, select
from typing import Optional, Tuple
from ..models import License, LicenseUsage, LicenseTier, TIER_LIMITS

def generate_license_key(tier: str, email: str) -> str:
    """Generate a unique license key"""
    tier_prefix = tier[:3].upper()
    random_part = secrets.token_hex(8).upper()
    
    # Split into groups of 4
    parts = [random_part[i:i+4] for i in range(0, 16, 4)]
    key = f"{tier_prefix}-{'-'.join(parts)}"
    
    return key

def create_license(
    session: Session,
    email: str,
    tier: LicenseTier,
    gumroad_order_id: Optional[str] = None
) -> License:
    """Create a new license"""
    license_key = generate_license_key(tier.value, email)
    
    license = License(
        license_key=license_key,
        tier=tier.value,
        email=email,
        is_active=True,
        gumroad_order_id=gumroad_order_id,
        activated_at=datetime.utcnow()
    )
    
    session.add(license)
    session.commit()
    session.refresh(license)
    
    return license

def validate_license(session: Session, license_key: str) -> Tuple[bool, Optional[License], Optional[str]]:
    """
    Validate a license key
    Returns: (is_valid, license_obj, error_message)
    """
    statement = select(License).where(License.license_key == license_key)
    license = session.exec(statement).first()
    
    if not license:
        return False, None, "Invalid license key"
    
    if not license.is_active:
        return False, license, "License has been deactivated"
    
    if license.expires_at and license.expires_at < datetime.utcnow():
        return False, license, "License has expired"
    
    return True, license, None

def check_usage_limit(
    session: Session,
    license_key: str,
    tier: LicenseTier
) -> Tuple[bool, int, int]:
    """
    Check if license has exceeded monthly usage
    Returns: (has_quota, used_count, limit)
    """
    now = datetime.utcnow()
    year, month = now.year, now.month
    
    # Get or create usage record for current month
    statement = select(LicenseUsage).where(
        LicenseUsage.license_key == license_key,
        LicenseUsage.year == year,
        LicenseUsage.month == month
    )
    usage = session.exec(statement).first()
    
    if not usage:
        usage = LicenseUsage(
            license_key=license_key,
            year=year,
            month=month,
            meetings_used=0
        )
        session.add(usage)
        session.commit()
    
    tier_config = TIER_LIMITS[tier]
    limit = tier_config["meetings_per_month"]
    used = usage.meetings_used
    
    has_quota = used < limit
    return has_quota, used, limit

def increment_usage(session: Session, license_key: str):
    """Increment monthly usage counter"""
    now = datetime.utcnow()
    year, month = now.year, now.month
    
    statement = select(LicenseUsage).where(
        LicenseUsage.license_key == license_key,
        LicenseUsage.year == year,
        LicenseUsage.month == month
    )
    usage = session.exec(statement).first()
    
    if usage:
        usage.meetings_used += 1
    else:
        usage = LicenseUsage(
            license_key=license_key,
            year=year,
            month=month,
            meetings_used=1
        )
        session.add(usage)
    
    session.commit()

def get_license_info(session: Session, license_key: str) -> dict:
    """Get complete license information"""
    is_valid, license, error = validate_license(session, license_key)
    
    if not is_valid:
        return {
            "valid": False,
            "error": error
        }
    
    # Convert string to enum
    tier_enum = LicenseTier(license.tier)
    tier_config = TIER_LIMITS[tier_enum]
    has_quota, used, limit = check_usage_limit(session, license_key, tier_enum)
    
    return {
        "valid": True,
        "license_key": license_key,
        "email": license.email,
        "tier": license.tier,
        "tier_name": tier_config["name"],
        "max_file_size_mb": tier_config["max_file_size_mb"],
        "meetings_used": used,
        "meetings_limit": limit,
        "has_quota": has_quota,
        "activated_at": license.activated_at.isoformat() if license.activated_at else None,
        "is_active": license.is_active
    }

def deactivate_license(session: Session, license_key: str) -> bool:
    """Deactivate a license"""
    statement = select(License).where(License.license_key == license_key)
    license = session.exec(statement).first()
    
    if license:
        license.is_active = False
        session.commit()
        return True
    
    return False

def validate_file_size(file_size_bytes: int, tier: LicenseTier) -> Tuple[bool, str]:
    """Validate if file size is within tier limits"""
    tier_config = TIER_LIMITS[tier]
    max_size_bytes = tier_config["max_file_size_mb"] * 1024 * 1024
    
    if file_size_bytes > max_size_bytes:
        file_size_mb = file_size_bytes / (1024 * 1024)
        max_size_mb = tier_config["max_file_size_mb"]
        return False, f"File size ({file_size_mb:.1f}MB) exceeds your tier limit of {max_size_mb}MB. Please upgrade your license."
    
    return True, ""