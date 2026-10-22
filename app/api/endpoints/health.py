from datetime import datetime, timezone
from fastapi import APIRouter, status

from app.core.config import settings
from app.db.mongodb import mongo_manager
from app.schemas.health import DatabaseHealth, HealthCheckResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Returns the current operational status of the service and MongoDB database connectivity.",
)
async def health_check() -> HealthCheckResponse:
    """
    Check the health of the application and its dependencies (MongoDB).
    """
    db_status = await mongo_manager.ping(timeout_seconds=1.5)
    is_connected = db_status.get("connected", False)

    # Status can be 'healthy' if DB is reachable, or 'degraded' if DB is disconnected
    overall_status = "healthy" if is_connected else "degraded"

    return HealthCheckResponse(
        status=overall_status,
        app_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        database=DatabaseHealth(
            connected=is_connected,
            latency_ms=db_status.get("latency_ms"),
            database=db_status.get("database"),
            error=db_status.get("error"),
        ),
    )
