import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check_endpoint():
    """
    Verify that the /api/v1/health endpoint responds with 200 OK and valid health metadata.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded"]
        assert "app_name" in data
        assert "version" in data
        assert "environment" in data
        assert "database" in data
        assert "connected" in data["database"]
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_root_endpoint():
    """
    Verify that root / returns 200 OK and service links.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "documentation" in data
        assert data["documentation"] == "/docs"
        assert data["health_check"] == "/api/v1/health"
