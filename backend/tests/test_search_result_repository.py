from collections.abc import AsyncIterator

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import JobSource, SearchLanguage, SearchSource
from app.db.models import SearchQuery
from app.domain.sourcing.types import (
    ParsedManualSearchResult,
    SearchResultFilters,
    SearchResultSort,
)
from app.repositories.jobs import JobRepository
from app.repositories.search_results import SearchResultRepository


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as database_session:
        yield database_session
    await engine.dispose()


async def query(session: AsyncSession, key: str) -> SearchQuery:
    job = await JobRepository().create(
        session,
        data={
            "source": JobSource.MANUAL,
            "company_name": f"Company {key}",
            "title": "Developer",
            "description_raw": "Description",
        },
    )
    record = SearchQuery(
        job_id=job.id,
        source=SearchSource.MANUAL,
        language=SearchLanguage.EN,
        query_text=key,
        normalized_query_key=key,
    )
    session.add(record)
    await session.flush()
    return record


def parsed(url: str, domain: str = "example.com") -> ParsedManualSearchResult:
    return ParsedManualSearchResult(url, url, domain, title="Demo Result")


async def test_create_list_filter_count_and_distinct(session: AsyncSession) -> None:
    first_query = await query(session, "q1")
    repository = SearchResultRepository()
    created = await repository.create_many(
        session,
        query_id=first_query.id,
        results=(
            parsed("https://example.com/a"),
            parsed("https://github.com/b", "github.com"),
        ),
        canonical={},
    )
    created[1].pre_score = 75
    await session.flush()

    listed = await repository.list_by_query(
        session,
        query_id=first_query.id,
        offset=0,
        limit=10,
        filters=SearchResultFilters(source_domain="github.com", min_pre_score=50),
        sort=SearchResultSort(),
    )

    assert [item.normalized_url for item in listed] == ["https://github.com/b"]
    assert (
        await repository.count_by_query(
            session, query_id=first_query.id, filters=SearchResultFilters()
        )
        == 2
    )
    assert (
        await repository.count_by_job(
            session, job_id=first_query.job_id, filters=SearchResultFilters()
        )
        == 2
    )
    assert (
        await repository.get_distinct_normalized_url_count(session, job_id=first_query.job_id) == 2
    )


async def test_same_query_unique_and_cross_query_canonical(session: AsyncSession) -> None:
    first_query = await query(session, "first")
    second_query = await query(session, "second")
    repository = SearchResultRepository()
    first = await repository.create_many(
        session,
        query_id=first_query.id,
        results=(parsed("https://example.com/profile"),),
        canonical={},
    )
    canonical = await repository.find_canonical_by_normalized_urls(
        session,
        urls={"https://example.com/profile"},
        exclude_query_id=second_query.id,
    )
    second = await repository.create_many(
        session,
        query_id=second_query.id,
        results=(parsed("https://example.com/profile"),),
        canonical=canonical,
    )

    assert canonical["https://example.com/profile"] is first[0]
    assert second[0].is_duplicate is True
    assert second[0].duplicate_of_id == first[0].id

    with pytest.raises(IntegrityError):
        await repository.create_many(
            session,
            query_id=first_query.id,
            results=(parsed("https://example.com/profile"),),
            canonical={},
        )
    await session.rollback()


async def test_delete_by_query_removes_results(session: AsyncSession) -> None:
    search_query = await query(session, "delete")
    repository = SearchResultRepository()
    await repository.create_many(
        session,
        query_id=search_query.id,
        results=(parsed("https://example.com/delete"),),
        canonical={},
    )

    await repository.delete_by_query(session, search_query.id)

    assert (
        await repository.count_by_query(
            session, query_id=search_query.id, filters=SearchResultFilters()
        )
        == 0
    )


async def test_duplicate_marking_empty_lookup_and_job_filters(session: AsyncSession) -> None:
    first_query = await query(session, "filter-first")
    second_query = await query(session, "filter-second")
    repository = SearchResultRepository()
    canonical = (
        await repository.create_many(
            session,
            query_id=first_query.id,
            results=(parsed("https://example.com/canonical"),),
            canonical={},
        )
    )[0]
    candidate = (
        await repository.create_many(
            session,
            query_id=second_query.id,
            results=(parsed("https://example.com/candidate"),),
            canonical={},
        )
    )[0]
    await repository.mark_duplicates(session, records=(candidate,), canonical=canonical)

    assert (
        await repository.find_existing_urls_for_query(session, query_id=first_query.id, urls=())
        == set()
    )
    assert (
        await repository.find_canonical_by_normalized_urls(
            session, urls=(), exclude_query_id=second_query.id
        )
        == {}
    )
    filtered = await repository.list_by_job(
        session,
        job_id=second_query.job_id,
        offset=0,
        limit=10,
        filters=SearchResultFilters(
            query_id=second_query.id,
            is_duplicate=True,
            candidate_assigned=False,
            language=SearchLanguage.EN,
        ),
        sort=SearchResultSort(),
    )
    assert filtered == [candidate]
    await repository.delete(session, result=candidate)
