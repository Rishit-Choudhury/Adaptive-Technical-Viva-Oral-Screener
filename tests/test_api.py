import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app


@pytest.mark.asyncio
async def test_not_found_handling():
    """
    Verify that an unmapped endpoint returns a structured 404 JSON response.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/non-existent-route")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert data["status_code"] == 404


def test_settings_initialization():
    """
    Verify that application configuration initializes with valid default parameters.
    """
    settings = get_settings()
    assert settings.PROJECT_NAME == "Adaptive Technical Viva & Oral Screener"
    assert settings.VERSION == "0.1.0"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.PORT == 8000
