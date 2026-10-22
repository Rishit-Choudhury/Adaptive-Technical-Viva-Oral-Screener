from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    """Schema representing database connectivity health."""
    connected: bool = Field(
        ...,
        description="Indicates if the database is reachable"
    )
    latency_ms: Optional[float] = Field(
        default=None,
        description="Ping response time in milliseconds"
    )
    database: Optional[str] = Field(
        default=None,
        description="Configured database name"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error details if connection failed"
    )


class HealthCheckResponse(BaseModel):
    """Schema representing overall application health status."""
    status: str = Field(
        ...,
        description="Overall service health status ('healthy', 'degraded', 'unhealthy')"
    )
    app_name: str = Field(
        ...,
        description="Application name"
    )
    version: str = Field(
        ...,
        description="Application release version"
    )
    environment: str = Field(
        ...,
        description="Current runtime environment (e.g., development, production)"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the health check"
    )
    database: DatabaseHealth = Field(
        ...,
        description="MongoDB connection details"
    )
