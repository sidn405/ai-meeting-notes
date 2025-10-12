"""
License Middleware for SQLModel
Add this as middleware/license.py
"""
from fastapi import Depends, HTTPException, Cookie
from sqlmodel import Session
from typing import Optional, Tuple

from ..db import get_session  # Your existing get_session function
from ..services.license import (
    validate_license,
    check_usage_limit,
    get_license_info,
    validate_file_size,
    increment_usage,
    LicenseTier,
    TIER_LIMITS
)
from ..models import License

class LicenseRequired:
    """Dependency for routes that require a valid license"""
    
    def __call__(
        self,
        license_key: Optional[str] = Cookie(None),
        session: Session = Depends(get_session)
    ) -> Tuple[License, dict]:
        """
        Validates license and returns (license_obj, tier_config)
        Raises HTTPException if invalid
        """
        if not license_key:
            raise HTTPException(
                status_code=401,
                detail="No license key found. Please activate your license at /activate"
            )
        
        is_valid, license, error = validate_license(session, license_key)
        
        if not is_valid:
            raise HTTPException(
                status_code=403,
                detail=f"License error: {error}"
            )
        
        # Convert string to enum
        tier_enum = LicenseTier(license.tier)
        
        # Check monthly usage quota
        has_quota, used, limit = check_usage_limit(session, license_key, tier_enum)
        
        if not has_quota:
            raise HTTPException(
                status_code=429,
                detail=f"Monthly quota exceeded ({used}/{limit} meetings used). Upgrade your license or wait until next month."
            )
        
        tier_config = TIER_LIMITS[tier_enum]
        
        return license, tier_config

# Create instance to use as dependency
require_license = LicenseRequired()

def track_meeting_usage(session: Session, license_key: str):
    """
    Increment usage counter after successful meeting processing
    Call this after a meeting is successfully created
    """
    increment_usage(session, license_key)

# Optional: Dependency to get license info without requiring it
def get_optional_license_info(
    license_key: Optional[str] = Cookie(None),
    session: Session = Depends(get_session)
) -> Optional[dict]:
    """Get license info if available, None otherwise"""
    if not license_key:
        return None
    
    return get_license_info(session, license_key)