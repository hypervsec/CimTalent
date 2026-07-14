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
async def client() -> AsyncIterator[AsyncClient]:
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
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    application = create_app(Settings(app_env="test", _env_file=None))
    application.dependency_overrides[get_db_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://test",
    ) as api_client:
        yield api_client
    await engine.dispose()


async def create_job(client: AsyncClient, parse: bool = True) -> dict[str, object]:
    created = await client.post(
        "/api/v1/jobs",
        json={
            "company_name": "Query API Company",
            "title": "Backend Developer",
            "description_raw": "Requirements:\n- Python and SQL required.\nLocation:\n- Bursa",
            "city": "Bursa",
        },
    )
    assert created.status_code == 201
    body = cast(dict[str, object], created.json())
    if parse:
        parsed = await client.post(f"/api/v1/jobs/{body['id']}/parse")
        assert parsed.status_code == 200
    return body


async def test_generate_list_get_delete_and_google_url(client: AsyncClient) -> None:
    job = await create_job(client)
    url = f"/api/v1/jobs/{job['id']}/queries/generate"

    generated = await client.post(url, json={"max_queries": 4})
    repeated = await client.post(url, json={"max_queries": 4})
    listed = await client.get(f"/api/v1/jobs/{job['id']}/queries")
    query_id = generated.json()["queries"][0]["id"]
    fetched = await client.get(f"/api/v1/queries/{query_id}")
    deleted = await client.delete(f"/api/v1/queries/{query_id}")

    assert generated.status_code == repeated.status_code == 200
    generated_count = generated.json()["generated_count"]
    assert 1 <= generated_count <= 4
    assert generated.json()["created_count"] == generated_count
    assert repeated.json()["created_count"] == 0
    assert repeated.json()["existing_count"] == generated_count
    assert generated.json()["queries"][0]["google_search_url"].startswith(
        "https://www.google.com/search?q="
    )
    assert listed.json()["total_items"] == generated_count
    assert fetched.status_code == 200
    assert deleted.status_code == 204


async def test_draft_missing_and_invalid_domain_errors(client: AsyncClient) -> None:
    draft = await create_job(client, parse=False)

    draft_response = await client.post(f"/api/v1/jobs/{draft['id']}/queries/generate", json={})
    missing = await client.post(
        f"/api/v1/jobs/{uuid4()}/queries/generate",
        json={},
        headers={"x-request-id": "missing-query-job"},
    )
    invalid = await client.post(
        f"/api/v1/jobs/{draft['id']}/queries/generate",
        json={"target_domain": "javascript:alert(1)"},
    )

    assert draft_response.status_code == 409
    assert draft_response.json()["error"]["code"] == "job_not_parsed"
    assert missing.status_code == 404
    assert missing.json()["error"]["request_id"] == "missing-query-job"
    assert invalid.status_code == 422


async def test_missing_query_and_openapi(client: AsyncClient) -> None:
    missing = await client.get(f"/api/v1/queries/{uuid4()}")
    schema = (await client.get("/openapi.json")).json()

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "search_query_not_found"
    assert "/api/v1/jobs/{job_id}/queries/generate" in schema["paths"]
