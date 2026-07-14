from collections.abc import AsyncIterator
from typing import Any
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


async def create_query(client: AsyncClient) -> tuple[str, str]:
    job = await client.post(
        "/api/v1/jobs",
        json={
            "company_name": "Import API Company",
            "title": "Backend Developer",
            "description_raw": "Requirements:\n- Python required.\nLocation:\n- Bursa",
            "city": "Bursa",
        },
    )
    job_id = job.json()["id"]
    assert (await client.post(f"/api/v1/jobs/{job_id}/parse")).status_code == 200
    generated = await client.post(
        f"/api/v1/jobs/{job_id}/queries/generate", json={"max_queries": 2}
    )
    return job_id, generated.json()["queries"][0]["id"]


@pytest.mark.parametrize(
    ("import_format", "payload"),
    [
        (
            "json",
            [
                {
                    "url": "https://linkedin.com/in/demo-api?trk=x",
                    "title": "Demo Candidate One - Engineer | LinkedIn",
                    "rank": 1,
                }
            ],
        ),
        ("urls", ["https://github.com/example-api"]),
        (
            "html",
            '<article><a href="https://example.com/api-profile">Test Profile</a></article>',
        ),
    ],
)
async def test_import_formats_and_result_endpoints(
    client: AsyncClient, import_format: str, payload: object
) -> None:
    job_id, query_id = await create_query(client)

    imported = await client.post(
        f"/api/v1/queries/{query_id}/import-results",
        json={"format": import_format, "mode": "merge", "payload": payload},
    )
    query_results = await client.get(f"/api/v1/queries/{query_id}/results")
    job_results = await client.get(f"/api/v1/jobs/{job_id}/search-results", params={"page_size": 1})
    result_id = imported.json()["results"][0]["id"]
    fetched = await client.get(f"/api/v1/search-results/{result_id}")

    assert imported.status_code == 200
    assert imported.json()["inserted_count"] == 1
    assert query_results.json()["total_items"] == 1
    assert job_results.json()["page_size"] == 1
    assert fetched.status_code == 200


async def test_repeated_merge_replace_duplicate_and_delete(client: AsyncClient) -> None:
    _, query_id = await create_query(client)
    request = {
        "format": "urls",
        "mode": "merge",
        "payload": [
            "https://linkedin.com/in/test-profile",
            "https://tr.linkedin.com/in/test-profile?trk=x",
        ],
    }

    first = await client.post(f"/api/v1/queries/{query_id}/import-results", json=request)
    second = await client.post(f"/api/v1/queries/{query_id}/import-results", json=request)
    result_id = first.json()["results"][0]["id"]
    deleted = await client.delete(f"/api/v1/search-results/{result_id}")

    assert first.json()["inserted_count"] == 1
    assert first.json()["duplicate_count"] == 1
    assert second.json()["inserted_count"] == 0
    assert deleted.status_code == 204


async def test_import_errors_request_id_and_no_html_leak(client: AsyncClient) -> None:
    _, query_id = await create_query(client)
    secret_html = "<script>super-secret-payload</script>"
    invalid = await client.post(
        f"/api/v1/queries/{query_id}/import-results",
        json={"format": "urls", "payload": secret_html},
        headers={"x-request-id": "invalid-import-request"},
    )
    missing_query = await client.post(
        f"/api/v1/queries/{uuid4()}/import-results",
        json={"format": "urls", "payload": []},
    )
    missing_result = await client.get(f"/api/v1/search-results/{uuid4()}")

    assert invalid.status_code == 422
    assert invalid.headers["x-request-id"] == "invalid-import-request"
    assert "super-secret-payload" not in invalid.text
    assert missing_query.status_code == 404
    assert missing_result.status_code == 404


async def test_too_large_html_is_413(client: AsyncClient) -> None:
    _, query_id = await create_query(client)
    response = await client.post(
        f"/api/v1/queries/{query_id}/import-results",
        json={"format": "html", "payload": "x" * (2 * 1024 * 1024 + 1)},
    )

    assert response.status_code == 413
