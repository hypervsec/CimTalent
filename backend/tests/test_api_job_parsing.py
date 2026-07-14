from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.enums import JobSource
from app.db.session import get_db_session
from app.main import create_app
from app.repositories.jobs import JobRepository


@dataclass(frozen=True)
class ApiContext:
    client: AsyncClient
    sessions: async_sessionmaker[AsyncSession]


@pytest.fixture
async def api() -> AsyncIterator[ApiContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: Any, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    application = create_app(Settings(app_env="test", _env_file=None))
    application.dependency_overrides[get_db_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield ApiContext(client, sessions)
    application.dependency_overrides.clear()
    await engine.dispose()


def payload(description: str | None = None) -> dict[str, object]:
    return {
        "company_name": "Parser Test Company",
        "title": "Yazılım Geliştirme Uzmanı",
        "description_raw": description
        or """
Zorunlu:
- En az 2 yıl Python, FastAPI ve PostgreSQL deneyimi.
- Bilgisayar Mühendisliği lisans mezunu.
- İyi derecede İngilizce.
Tercihen:
- Docker bilgisi.
Lokasyon:
- Bursa / Hibrit
""",
        "city": "Bursa",
        "country": "Türkiye",
    }


async def create_job(client: AsyncClient, description: str | None = None) -> dict[str, object]:
    response = await client.post("/api/v1/jobs", json=payload(description))
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


async def test_parse_returns_schema_and_persisted_requirements(api: ApiContext) -> None:
    created = await create_job(api.client)

    parsed = await api.client.post(f"/api/v1/jobs/{created['id']}/parse")
    requirements = await api.client.get(f"/api/v1/jobs/{created['id']}/requirements")
    job = await api.client.get(f"/api/v1/jobs/{created['id']}")

    assert parsed.status_code == 200
    body = parsed.json()
    assert body["job_id"] == created["id"]
    assert body["status"] == "parsed"
    assert body["parser_version"] == "rule-based-v1"
    assert body["created_requirement_count"] == len(body["requirements"])
    assert 0 <= body["confidence"] <= 1
    expected_fields = {
        "type",
        "raw_value",
        "normalized_value",
        "importance",
        "weight",
        "confidence",
        "source",
        "evidence_text",
    }
    assert expected_fields == set(body["requirements"][0])
    assert requirements.status_code == 200
    assert len(requirements.json()) == body["created_requirement_count"]
    assert job.json()["requirement_count"] == body["created_requirement_count"]
    assert job.json()["required_skills"]


async def test_repeated_parse_does_not_duplicate(api: ApiContext) -> None:
    created = await create_job(api.client)
    url = f"/api/v1/jobs/{created['id']}/parse"

    first = await api.client.post(url)
    second = await api.client.post(url)
    requirements = await api.client.get(f"/api/v1/jobs/{created['id']}/requirements")

    assert first.status_code == second.status_code == 200
    assert first.json()["created_requirement_count"] == second.json()["created_requirement_count"]
    assert len(requirements.json()) == second.json()["created_requirement_count"]


async def test_parse_missing_job_returns_request_id(api: ApiContext) -> None:
    response = await api.client.post(
        f"/api/v1/jobs/{uuid4()}/parse",
        headers={"x-request-id": "parse-missing-request"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"
    assert response.json()["error"]["request_id"] == "parse-missing-request"


async def test_archived_job_is_rejected(api: ApiContext) -> None:
    created = await create_job(api.client)
    archived = await api.client.patch(f"/api/v1/jobs/{created['id']}", json={"status": "archived"})

    response = await api.client.post(f"/api/v1/jobs/{created['id']}/parse")

    assert archived.status_code == 200
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "job_parse_invalid_state"


async def test_empty_description_is_422_and_does_not_leak_description(
    api: ApiContext,
) -> None:
    secret_description = "   "
    async with api.sessions() as session:
        job = await JobRepository().create(
            session,
            data={
                "source": JobSource.MANUAL,
                "company_name": "Empty",
                "title": "Developer",
                "description_raw": secret_description,
            },
        )
        await session.commit()
        job_id: UUID = job.id

    response = await api.client.post(
        f"/api/v1/jobs/{job_id}/parse",
        headers={"x-request-id": "empty-description-request"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_job_description"
    assert response.json()["error"]["request_id"] == "empty-description-request"
    assert secret_description not in response.text


async def test_parse_endpoint_is_in_openapi(api: ApiContext) -> None:
    response = await api.client.get("/openapi.json")

    assert response.status_code == 200
    assert "post" in response.json()["paths"]["/api/v1/jobs/{job_id}/parse"]
