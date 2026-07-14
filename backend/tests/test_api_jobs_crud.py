from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.db.session import get_db_session
from app.main import create_app


@pytest.fixture
async def api_client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: Any, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    application = create_app(Settings(app_env="test", _env_file=None))
    application.dependency_overrides[get_db_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield client
    application.dependency_overrides.clear()
    await engine.dispose()


def job_payload(
    company: str = "Example Company",
    title: str = "Backend Developer",
    **changes: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "company_name": company,
        "title": title,
        "description_raw": f"Build services for {company}",
        "city": "Bursa",
        "required_skills": ["Python", "SQL"],
    }
    payload.update(changes)
    return payload


async def create_job(
    client: AsyncClient,
    company: str = "Example Company",
    title: str = "Backend Developer",
    **changes: object,
) -> dict[str, object]:
    payload = job_payload(company=company, title=title)
    payload.update(changes)
    response = await client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


async def test_create_job_returns_public_schema_and_utc_dates(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post("/api/v1/jobs", json=job_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["company_name"] == "Example Company"
    assert body["status"] == "draft"
    assert body["required_skills"] == ["Python", "SQL"]
    assert body["created_at"].endswith("Z")
    assert body["requirement_count"] == 0
    assert body["search_query_count"] == 0
    assert body["candidate_match_count"] == 0
    assert body["shortlist_count"] == 0
    assert "_sa_instance_state" not in body
    assert response.headers["x-request-id"]


async def test_create_validation_and_duplicate_error_format(
    api_client: AsyncClient,
) -> None:
    invalid = await api_client.post("/api/v1/jobs", json=job_payload(company=" "))
    assert invalid.status_code == 422

    await create_job(api_client)
    duplicate = await api_client.post(
        "/api/v1/jobs",
        json=job_payload(
            company=" example company ",
            title="BACKEND DEVELOPER",
            description_raw="Build services for Example Company",
        ),
        headers={"x-request-id": "test-request-id"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"] == {
        "code": "duplicate_job",
        "message": "A matching job posting already exists.",
        "details": {"existing_job_id": duplicate.json()["error"]["details"]["existing_job_id"]},
        "request_id": "test-request-id",
    }


async def test_list_pagination_empty_page_and_limits(api_client: AsyncClient) -> None:
    for company in ("Alpha", "Bravo", "Charlie"):
        await create_job(api_client, company=company)

    first = await api_client.get("/api/v1/jobs", params={"page": 1, "page_size": 2})
    beyond = await api_client.get("/api/v1/jobs", params={"page": 5, "page_size": 2})
    invalid_size = await api_client.get("/api/v1/jobs", params={"page_size": 101})

    assert first.status_code == 200
    assert len(first.json()["items"]) == 2
    assert first.json()["page"] == 1
    assert first.json()["page_size"] == 2
    assert first.json()["total_items"] == 3
    assert first.json()["total_pages"] == 2
    assert first.json()["has_next"] is True
    assert first.json()["has_previous"] is False
    assert beyond.status_code == 200
    assert beyond.json()["items"] == []
    assert beyond.json()["has_previous"] is True
    assert invalid_size.status_code == 422


async def test_list_filter_search_and_sort(api_client: AsyncClient) -> None:
    await create_job(api_client, company="Alpha", city="Bursa")
    await create_job(
        api_client,
        company="Zulu",
        title="Welding Engineer",
        city="Istanbul",
        source="linkedin",
        source_url="https://example.test/jobs/2",
    )

    filtered = await api_client.get("/api/v1/jobs", params={"city": " bursa "})
    searched = await api_client.get("/api/v1/jobs", params={"search": "welding"})
    sorted_response = await api_client.get(
        "/api/v1/jobs",
        params={"sort_by": "company_name", "sort_direction": "desc"},
    )
    invalid_sort = await api_client.get("/api/v1/jobs", params={"sort_by": "drop table"})

    assert [item["company_name"] for item in filtered.json()["items"]] == ["Alpha"]
    assert [item["company_name"] for item in searched.json()["items"]] == ["Zulu"]
    assert [item["company_name"] for item in sorted_response.json()["items"]] == [
        "Zulu",
        "Alpha",
    ]
    assert invalid_sort.status_code == 422


async def test_get_existing_and_missing_job(api_client: AsyncClient) -> None:
    created = await create_job(api_client)

    found = await api_client.get(f"/api/v1/jobs/{created['id']}")
    missing = await api_client.get(f"/api/v1/jobs/{uuid4()}")

    assert found.status_code == 200
    assert found.json()["id"] == created["id"]
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "job_not_found"


async def test_patch_partial_explicit_null_and_json_round_trip(
    api_client: AsyncClient,
) -> None:
    created = await create_job(api_client)

    updated = await api_client.patch(
        f"/api/v1/jobs/{created['id']}",
        json={"title": "Senior Backend Developer", "city": None, "languages": ["English"]},
    )
    reloaded = await api_client.get(f"/api/v1/jobs/{created['id']}")

    assert updated.status_code == 200
    assert updated.json()["title"] == "Senior Backend Developer"
    assert updated.json()["city"] is None
    assert reloaded.json()["languages"] == ["English"]


async def test_patch_invalid_transition_and_missing_job(api_client: AsyncClient) -> None:
    created = await create_job(api_client)

    invalid = await api_client.patch(f"/api/v1/jobs/{created['id']}", json={"status": "completed"})
    missing = await api_client.patch(f"/api/v1/jobs/{uuid4()}", json={"title": "Missing"})

    assert invalid.status_code == 409
    assert invalid.json()["error"]["code"] == "invalid_job_status_transition"
    assert missing.status_code == 404


async def test_delete_existing_and_missing_job(api_client: AsyncClient) -> None:
    created = await create_job(api_client)

    deleted = await api_client.delete(f"/api/v1/jobs/{created['id']}")
    missing = await api_client.delete(f"/api/v1/jobs/{created['id']}")

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert missing.status_code == 404


async def test_requirements_existing_and_missing_job(api_client: AsyncClient) -> None:
    created = await create_job(api_client)

    existing = await api_client.get(f"/api/v1/jobs/{created['id']}/requirements")
    missing = await api_client.get(f"/api/v1/jobs/{uuid4()}/requirements")

    assert existing.status_code == 200
    assert existing.json() == []
    assert missing.status_code == 404


async def test_jobs_are_present_in_openapi(api_client: AsyncClient) -> None:
    response = await api_client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert set(paths["/api/v1/jobs"]) >= {"get", "post"}
    assert set(paths["/api/v1/jobs/{job_id}"]) >= {"get", "patch", "delete"}
    assert "/api/v1/jobs/{job_id}/requirements" in paths
