"""
Central API router re-exporting the v1 API router.
"""
from app.api.api_v1.api import api_router

__all__ = ["api_router"]
