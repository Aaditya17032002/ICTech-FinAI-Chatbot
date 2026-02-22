import logging
from datetime import datetime

from fastapi import APIRouter

from app.config import get_settings
from app.models.schemas import HealthResponse
from app.repositories.cache_repository import get_cache_repository

router = APIRouter(tags=["Health"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns basic service health status and version information.
    """
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.utcnow(),
    )


@router.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@router.post("/reset")
async def reset_application():
    """
    Reset the application by clearing all caches.
    
    This clears:
    - Response cache (chat responses)
    - Session cache
    - Fund data cache
    
    Returns confirmation of cache clear.
    """
    try:
        cache = get_cache_repository()
        cache.clear()
        logger.info("[RESET] All caches cleared successfully")
        return {
            "status": "success",
            "message": "All caches cleared successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"[RESET] Error clearing cache: {e}")
        return {
            "status": "error",
            "message": f"Failed to clear cache: {str(e)}",
            "timestamp": datetime.utcnow().isoformat(),
        }
