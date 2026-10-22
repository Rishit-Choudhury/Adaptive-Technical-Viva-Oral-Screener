from fastapi import Header, HTTPException, status
from app.core.config import settings


def verify_admin_api_key(
    x_admin_key: str = Header(default="", alias="X-Admin-Key", description="Admin security key for restricted operations")
) -> bool:
    """
    Security dependency to protect dataset import and privileged administrative endpoints.
    """
    if not settings.ADMIN_API_KEY:
        return True  # If empty in dev, allow

    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing administrative key (X-Admin-Key header required).",
        )
    return True
