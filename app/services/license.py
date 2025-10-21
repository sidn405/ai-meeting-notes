"""
License Service for SQLModel - Now supports both manual licenses and IAP
Add this as services/license.py
"""
import secrets
import re
from datetime import datetime
from sqlmodel import Session, select
from typing import Optional, Tuple
from ..models import License, LicenseUsage, LicenseTier, TIER_LIMITS

def generate_license_key(tier: str, email: str, prefix: str = "") -> str:
    tier_map = {"starter": "STA", "professional": "PRO", "business": "BUS"}
    head = (prefix or tier_map.get((tier or "").lower(), "KEY")).upper()

    # 16 hex chars -> 4-4-4-4 groups
    rand = secrets.token_hex(8).upper()  # e.g. 1F2A9C… (length 16)
    groups = "-".join([rand[i:i+4] for i in range(0, 16, 4)])
    return f"{head}-{groups}"

PATTERN_A = re.compile(r"^[A-Z]{3}-[A-Z0-9]{4}(?:-[A-Z0-9]{4}){3}$")   # BUS-XXXX-XXXX-XXXX-XXXX
PATTERN_B = re.compile(r"^[A-Z]{2,}-[A-Z0-9\-]{6,}$")                  # e.g. BUSINESS-<token>

def is_key_format_ok(key: str) -> bool:
    key = key.strip().upper()
    return bool(PATTERN_A.match(key) or PATTERN_B.match(key))

def create_license(
    session: Session,
    email: str,
    tier: LicenseTier,
    gumroad_order_id: Optional[str] = None,
    iap_purchase_token: Optional[str] = None,
    iap_store: Optional[str] = None,
    iap_product_id: Optional[str] = None
) -> License:
    """Create a new license (supports both manual and IAP)"""
    # Generate license key
    # For IAP licenses, use "IAP" prefix to distinguish
    prefix = "IAP" if iap_purchase_token else None
    license_key = generate_license_key(tier.value, email, prefix)
    
    license = License(
        license_key=license_key,
        tier=tier.value,
        email=email,
        is_active=True,
        gumroad_order_id=gumroad_order_id,
        activated_at=datetime.utcnow(),
        iap_purchase_token=iap_purchase_token,
        iap_store=iap_store,
        iap_product_id=iap_product_id
    )
    
    session.add(license)
    session.commit()
    session.refresh(license)
    
    return license

def find_license_by_iap_token(
    session: Session,
    purchase_token: str
) -> Optional[License]:
    """Find license by IAP purchase token"""
    statement = select(License).where(License.iap_purchase_token == purchase_token)
    return session.exec(statement).first()

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
        "expires_at": license.expires_at.isoformat() if license.expires_at else None,
        "is_active": license.is_active,
        "is_iap": license.iap_purchase_token is not None
    }
    
def update_iap_license(
    session: Session,
    purchase_token: str,
    expires_at: Optional[datetime] = None,
    is_active: bool = True
) -> Optional[License]:
    """Update an IAP license (for subscription renewals/cancellations)"""
    license = find_license_by_iap_token(session, purchase_token)
    
    if license:
        license.is_active = is_active
        license.expires_at = expires_at
        license.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(license)
        return license
    
    return None

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
    tier_str = tier.value if isinstance(tier, LicenseTier) else tier
    tier_config = TIER_LIMITS[tier]
    max_size_bytes = tier_config["max_file_size_mb"] * 1024 * 1024
    
    if file_size_bytes > max_size_bytes:
        file_size_mb = file_size_bytes / (1024 * 1024)
        max_size_mb = tier_config["max_file_size_mb"]
        return False, f"File size ({file_size_mb:.1f}MB) exceeds your tier limit of {max_size_mb}MB. Please upgrade your license."
    
    return True, ""