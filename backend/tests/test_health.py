from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


async def test_health_endpoint() -> None:
    settings = Settings(app_env="test", _env_file=None)
    application = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "CimTalent AI",
        "environment": "test",
    }


async def test_openapi_exposes_health_endpoint() -> None:
    settings = Settings(app_env="test", _env_file=None)
    application = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/health" in response.json()["paths"]
