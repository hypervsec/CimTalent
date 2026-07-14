from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db_session
from app.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection: Any, _: object) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    await engine.dispose()


async def create_candidate(client: AsyncClient) -> str:
    response = await client.post("/api/v1/candidates", json={"full_name": "Demo Candidate"})
    assert response.status_code == 201
    return cast(str, response.json()["id"])


def enrichment_payload() -> dict[str, object]:
    return {
        "mode": "deep",
        "identity": {
            "headline": {"value": "Backend Engineer", "source": "manual"},
            "about": {"value": "Reliable profile", "source": "manual"},
        },
        "experiences": [
            {
                "external_key": "experience-1",
                "position_title_raw": "Backend Developer",
                "company_name": "Demo Co",
                "start_date": "2021-01-01",
                "is_current": True,
            }
        ],
        "educations": [{"institution_name": "Demo University"}],
        "skills": [{"raw_name": "Python"}, {"raw_name": "SQL Server"}, {"raw_name": "REST API"}],
        "languages": [{"language": "English", "proficiency": "fluent"}],
    }


async def test_preview_import_history_and_profile(client: AsyncClient) -> None:
    candidate_id = await create_candidate(client)
    preview = await client.post(
        f"/api/v1/candidates/{candidate_id}/enrichment/preview", json=enrichment_payload()
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["diff"]["experiences"]["create_count"] == 1
    before = await client.get(f"/api/v1/candidates/{candidate_id}/profile")
    assert before.status_code == 200
    assert before.json()["experiences"] == []

    imported = await client.post(
        f"/api/v1/candidates/{candidate_id}/enrichment/import", json=enrichment_payload()
    )
    assert imported.status_code == 200, imported.text
    body = imported.json()
    assert body["candidate"]["profile_status"] == "scraped"
    assert body["data_quality_after"] > body["data_quality_before"]
    run_id = body["run"]["id"]
    assert "identity" not in body["run"]["input_summary"]

    repeated = await client.post(
        f"/api/v1/candidates/{candidate_id}/enrichment/import", json=enrichment_payload()
    )
    assert repeated.status_code == 200
    assert repeated.json()["diff"]["experiences"]["create_count"] == 0

    runs = await client.get(f"/api/v1/candidates/{candidate_id}/enrichment-runs")
    assert runs.status_code == 200
    assert runs.json()["total_items"] == 2
    assert (await client.get(f"/api/v1/enrichment-runs/{run_id}")).status_code == 200
    missing_run = await client.get("/api/v1/enrichment-runs/00000000-0000-0000-0000-000000000099")
    assert missing_run.status_code == 404

    filtered = await client.get(
        f"/api/v1/candidates/{candidate_id}/enrichment-runs",
        params={
            "provider": "manual",
            "mode": "deep",
            "status": "completed",
            "sort_by": "completed_at",
            "sort_direction": "asc",
        },
    )
    assert filtered.status_code == 200
    assert filtered.json()["total_items"] == 2

    profile = await client.get(f"/api/v1/candidates/{candidate_id}/profile")
    assert profile.status_code == 200
    assert len(profile.json()["experiences"]) == 1
    assert len(profile.json()["skills"]) == 3
    assert profile.json()["latest_enrichment_run"] is not None


async def test_enrichment_errors_are_safe(client: AsyncClient) -> None:
    missing = "00000000-0000-0000-0000-000000000001"
    response = await client.post(
        f"/api/v1/candidates/{missing}/enrichment/preview",
        json=enrichment_payload(),
        headers={"x-request-id": "enrichment-test"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["request_id"] == "enrichment-test"

    candidate_id = await create_candidate(client)
    invalid = await client.post(
        f"/api/v1/candidates/{candidate_id}/enrichment/import",
        json={"experiences": [{"position_title_raw": "", "description": "secret"}]},
    )
    assert invalid.status_code == 422
    assert "secret" not in invalid.text

    unsupported = await client.post(
        f"/api/v1/candidates/{candidate_id}/enrichment/import",
        json={"provider": "linkedin"},
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "unsupported_enrichment_provider"

    oversized = await client.post(
        f"/api/v1/candidates/{candidate_id}/enrichment/import",
        json={},
        headers={"content-length": "2000001", "x-request-id": "oversized-test"},
    )
    assert oversized.status_code == 413
    assert oversized.json()["error"]["request_id"] == "oversized-test"
