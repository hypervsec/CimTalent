from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

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
from app.db.enums import JobSource, SearchLanguage, SearchSource
from app.db.models import SearchQuery, SearchResult
from app.db.session import get_db_session
from app.main import create_app
from app.repositories.jobs import JobRepository


@dataclass(frozen=True, slots=True)
class ApiContext:
    client: AsyncClient
    sessions: async_sessionmaker[AsyncSession]


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
async def context(engine: AsyncEngine) -> AsyncIterator[ApiContext]:
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    application = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    application.dependency_overrides[get_db_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        yield ApiContext(client, sessions)


async def seed_results(
    context: ApiContext,
    urls: list[str],
    *,
    source: SearchSource = SearchSource.GOOGLE_XRAY,
    job_id: UUID | None = None,
    query_key: str = "query",
) -> tuple[UUID, list[UUID]]:
    async with context.sessions() as session:
        if job_id is None:
            job = await JobRepository().create(
                session,
                data={
                    "source": JobSource.MANUAL,
                    "company_name": "Demo Company",
                    "title": "Backend Engineer",
                    "description_raw": "Build systems",
                },
            )
            job_id = job.id
        query = SearchQuery(
            job_id=job_id,
            source=source,
            language=SearchLanguage.EN,
            query_text=query_key,
            normalized_query_key=query_key,
        )
        session.add(query)
        await session.flush()
        records: list[SearchResult] = []
        for index, url in enumerate(urls):
            domain = (
                "linkedin.com"
                if "linkedin.com" in url
                else "github.com"
                if "github.com" in url
                else "example.com"
            )
            record = SearchResult(
                search_query_id=query.id,
                source_url=url,
                normalized_url=url,
                source_domain=domain,
                title="Demo Engineer - Profile",
                snippet="Public search discovery snippet",
                displayed_name="Demo Engineer",
                displayed_headline="Software Engineer at Demo Company",
                displayed_location="Bursa, Türkiye",
                result_rank=index + 1,
            )
            session.add(record)
            records.append(record)
        await session.commit()
        return job_id, [record.id for record in records]


async def test_single_discovery_creates_metadata_and_is_idempotent(context: ApiContext) -> None:
    _, result_ids = await seed_results(
        context, ["https://tr.linkedin.com/in/demo-engineer/?trk=public_profile"]
    )
    path = f"/api/v1/search-results/{result_ids[0]}/discover-candidate"
    first = await context.client.post(path)
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["action"] == "created"
    assert payload["candidate"]["normalized_profile_url"] == (
        "https://www.linkedin.com/in/demo-engineer"
    )
    assert payload["candidate"]["source"] == "google_xray"
    assert payload["candidate"]["discovery_snippet"] == "Public search discovery snippet"
    assert payload["candidate"]["about"] is None
    assert payload["candidate"]["city"] == "Bursa"
    assert payload["candidate"]["data_quality_score"] > 0

    repeated = await context.client.post(path)
    assert repeated.status_code == 200
    assert repeated.json()["action"] == "linked_existing"
    assert repeated.json()["was_already_linked"] is True
    assert repeated.json()["candidate_id"] == payload["candidate_id"]


async def test_same_profile_from_different_query_links_existing(context: ApiContext) -> None:
    job_id, first_ids = await seed_results(
        context, ["https://www.linkedin.com/in/same-person?trk=first"], query_key="first"
    )
    _, second_ids = await seed_results(
        context,
        ["https://tr.linkedin.com/in/same-person/?utm_source=second"],
        job_id=job_id,
        query_key="second",
    )
    first = await context.client.post(f"/api/v1/search-results/{first_ids[0]}/discover-candidate")
    second = await context.client.post(f"/api/v1/search-results/{second_ids[0]}/discover-candidate")
    assert second.status_code == 200
    assert second.json()["action"] == "linked_existing"
    assert second.json()["candidate_id"] == first.json()["candidate_id"]


@pytest.mark.parametrize(
    "url",
    [
        "https://linkedin.com/company/demo",
        "https://linkedin.com/jobs/view/123",
        "javascript:alert(1)",
    ],
)
async def test_single_ineligible_result_returns_safe_422(context: ApiContext, url: str) -> None:
    _, result_ids = await seed_results(context, [url])
    response = await context.client.post(
        f"/api/v1/search-results/{result_ids[0]}/discover-candidate",
        headers={"x-request-id": "discovery-safe"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "search_result_not_eligible"
    assert response.json()["error"]["request_id"] == "discovery-safe"


async def test_github_profile_is_eligible_imported_source(context: ApiContext) -> None:
    _, result_ids = await seed_results(
        context, ["https://github.com/demo-engineer"], source=SearchSource.MANUAL
    )
    response = await context.client.post(
        f"/api/v1/search-results/{result_ids[0]}/discover-candidate"
    )
    assert response.status_code == 200
    assert response.json()["confidence"] == 0.8
    assert response.json()["candidate"]["source"] == "imported"


async def test_bulk_dry_run_does_not_mutate_then_execute_deduplicates(
    context: ApiContext,
) -> None:
    job_id, _ = await seed_results(
        context,
        [
            "https://linkedin.com/in/bulk-person?trk=one",
            "https://tr.linkedin.com/in/bulk-person/?utm_source=two",
            "https://linkedin.com/company/not-a-person",
        ],
    )
    path = f"/api/v1/jobs/{job_id}/candidates/discover"
    dry_run = await context.client.post(path, json={"dry_run": True})
    assert dry_run.status_code == 200
    assert dry_run.json()["created_candidate_count"] == 1
    assert dry_run.json()["linked_existing_count"] == 1
    assert dry_run.json()["skipped_count"] == 1
    assert (await context.client.get("/api/v1/candidates")).json()["total_items"] == 0

    executed = await context.client.post(path, json={})
    assert executed.status_code == 200
    assert executed.json()["created_candidate_count"] == 1
    assert executed.json()["linked_existing_count"] == 1
    assert executed.json()["skipped_count"] == 1
    candidates = await context.client.get("/api/v1/candidates")
    assert candidates.json()["total_items"] == 1
    assert candidates.json()["items"][0]["search_result_count"] == 2


async def test_bulk_filters_limit_and_missing_job(context: ApiContext) -> None:
    job_id, _ = await seed_results(
        context,
        ["https://github.com/first", "https://example.com/second"],
    )
    response = await context.client.post(
        f"/api/v1/jobs/{job_id}/candidates/discover",
        json={"dry_run": True, "include_domains": ["github.com"], "max_results": 2},
    )
    assert response.status_code == 200
    assert response.json()["received_result_count"] == 2
    assert response.json()["candidate_eligible_count"] == 1

    missing = await context.client.post(f"/api/v1/jobs/{uuid4()}/candidates/discover", json={})
    assert missing.status_code == 404


async def test_missing_search_result(context: ApiContext) -> None:
    response = await context.client.post(f"/api/v1/search-results/{uuid4()}/discover-candidate")
    assert response.status_code == 404
