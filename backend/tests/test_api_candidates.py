from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db_session
from app.main import create_app


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    database = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(database.sync_engine, "connect")
    def enable_foreign_keys(connection: Any, _: object) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    async with database.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield database
    await database.dispose()


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    application = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    application.dependency_overrides[get_db_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as http_client:
        yield http_client


async def create_candidate(
    client: AsyncClient, name: str = "Demo Engineer", **values: object
) -> dict[str, Any]:
    payload: dict[str, object] = {"full_name": name}
    payload.update(values)
    response = await client.post("/api/v1/candidates", json=payload)
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


async def test_candidate_crud_list_quality_and_normalization(client: AsyncClient) -> None:
    created = await create_candidate(
        client,
        " Dr. Demo Engineer | LinkedIn ",
        primary_profile_url="https://tr.linkedin.com/in/demo-engineer/?trk=public_profile",
        headline="Software Engineer at Demo Company | LinkedIn",
        location_raw="Bursa, Türkiye",
    )
    assert created["full_name"] == "Demo Engineer"
    assert created["normalized_profile_url"] == "https://www.linkedin.com/in/demo-engineer"
    assert created["profile_slug"] == "demo-engineer"
    assert created["current_title"] == "Software Engineer"
    assert created["current_company"] == "Demo Company"
    assert (created["city"], created["country"]) == ("Bursa", "Turkey")
    assert created["data_quality_score"] == 70

    listed = await client.get(
        "/api/v1/candidates",
        params={"city": "Bursa", "search": "software", "sort_by": "data_quality_score"},
    )
    assert listed.status_code == 200
    assert listed.json()["total_items"] == 1
    assert listed.json()["items"][0]["search_result_count"] == 0

    patched = await client.patch(
        f"/api/v1/candidates/{created['id']}",
        json={"about": "  Reliable profile summary  ", "profile_status": "queued"},
    )
    assert patched.status_code == 200
    assert patched.json()["about"] == "Reliable profile summary"
    assert patched.json()["data_quality_score"] == 75

    quality = await client.get(f"/api/v1/candidates/{created['id']}/quality")
    assert quality.status_code == 200
    assert quality.json()["total_score"] == 75
    assert "education" in quality.json()["missing_fields"]

    fetched = await client.get(f"/api/v1/candidates/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["profile_status"] == "queued"

    deleted = await client.delete(f"/api/v1/candidates/{created['id']}")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/v1/candidates/{created['id']}")).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"full_name": "   "},
        {"full_name": "Profile"},
        {"primary_profile_url": "javascript:alert(1)"},
        {"primary_profile_url": "https://linkedin.com/company/demo"},
        {"full_name": "Demo", "source": "google_xray"},
    ],
)
async def test_invalid_create_is_safe_422(client: AsyncClient, payload: dict[str, object]) -> None:
    response = await client.post(
        "/api/v1/candidates", json=payload, headers={"x-request-id": "candidate-test"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["request_id"] == "candidate-test"
    assert "javascript" not in response.text


async def test_duplicate_url_and_invalid_status_transition(client: AsyncClient) -> None:
    first = await create_candidate(
        client,
        primary_profile_url="https://linkedin.com/in/example-candidate",
    )
    duplicate = await client.post(
        "/api/v1/candidates",
        json={
            "full_name": "Other Name",
            "primary_profile_url": "https://tr.linkedin.com/in/example-candidate/?trk=test",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["details"]["existing_candidate_id"] == first["id"]
    invalid = await client.patch(
        f"/api/v1/candidates/{first['id']}", json={"profile_status": "scraped"}
    )
    assert invalid.status_code == 409
    assert invalid.json()["error"]["code"] == "invalid_candidate_status_transition"


async def test_identity_cannot_be_fully_cleared(client: AsyncClient) -> None:
    created = await create_candidate(client)
    response = await client.patch(f"/api/v1/candidates/{created['id']}", json={"full_name": None})
    assert response.status_code == 422


async def test_duplicate_suggestions_need_supporting_fields(client: AsyncClient) -> None:
    base = await create_candidate(
        client,
        "Example Candidate",
        headline="Backend Engineer",
        city="Bursa",
    )
    supported = await create_candidate(
        client,
        "Example Candidate",
        headline="Backend Engineer",
        city="Bursa",
    )
    await create_candidate(client, "Example Candidate")
    response = await client.get(f"/api/v1/candidates/{base['id']}/duplicate-suggestions")
    assert response.status_code == 200
    assert response.json() == [
        {
            "candidate_id": supported["id"],
            "score": 0.95,
            "matched_fields": ["full_name", "headline", "city"],
            "reasons": ["exact_name_headline_city"],
        }
    ]


async def test_missing_candidate_endpoints(client: AsyncClient) -> None:
    missing = uuid4()
    for method, path in (
        (client.get, f"/api/v1/candidates/{missing}"),
        (client.get, f"/api/v1/candidates/{missing}/quality"),
        (client.get, f"/api/v1/candidates/{missing}/search-results"),
        (client.delete, f"/api/v1/candidates/{missing}"),
    ):
        response = await method(path)
        assert response.status_code == 404


async def test_merge_endpoint_dry_run_execute_and_conflict(client: AsyncClient) -> None:
    target = await create_candidate(client, "Merge Target")
    source = await create_candidate(client, "Merge Source", headline="Backend Engineer")
    path = f"/api/v1/candidates/{target['id']}/merge"
    dry_run = await client.post(
        path,
        json={
            "source_candidate_ids": [source["id"]],
            "field_strategy": "keep_target",
            "dry_run": True,
        },
    )
    assert dry_run.status_code == 200, dry_run.text
    assert dry_run.json()["dry_run"] is True
    assert (await client.get(f"/api/v1/candidates/{source['id']}")).status_code == 200

    merged = await client.post(
        path,
        json={
            "source_candidate_ids": [source["id"]],
            "field_strategy": "keep_target",
        },
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["candidate"]["headline"] == "Backend Engineer"
    assert (await client.get(f"/api/v1/candidates/{source['id']}")).status_code == 404

    self_merge = await client.post(
        path,
        json={"source_candidate_ids": [target["id"]]},
    )
    assert self_merge.status_code == 409
