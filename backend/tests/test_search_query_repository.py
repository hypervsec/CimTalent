from collections.abc import AsyncIterator

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import JobSource, SearchLanguage, SearchSource, SearchStatus
from app.db.models import JobPosting
from app.domain.jobs.types import SortDirection
from app.domain.sourcing.types import (
    GeneratedQuery,
    QueryType,
    SearchQueryFilters,
    SearchQuerySort,
    SearchQuerySortField,
)
from app.repositories.jobs import JobRepository
from app.repositories.search_queries import SearchQueryRepository


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as database_session:
        yield database_session
    await engine.dispose()


def generated(value: str, language: SearchLanguage = SearchLanguage.EN) -> GeneratedQuery:
    return GeneratedQuery(
        source=SearchSource.GOOGLE_XRAY,
        language=language,
        query_text=value,
        query_type=QueryType.TITLE_LOCATION,
        precision_level=3,
        expected_intent="title and location",
        included_titles=("Developer",),
        included_skills=(),
        included_locations=("Bursa",),
        normalized_query_key=value.casefold(),
    )


async def create_job(session: AsyncSession) -> JobPosting:
    return await JobRepository().create(
        session,
        data={
            "source": JobSource.MANUAL,
            "company_name": "Example",
            "title": "Developer",
            "description_raw": "Description",
        },
    )


async def test_create_list_filter_sort_and_existing_keys(session: AsyncSession) -> None:
    job = await create_job(session)
    repository = SearchQueryRepository()
    records = await repository.create_many(
        session,
        job_id=job.id,
        queries=(generated("Query B"), generated("Query A", SearchLanguage.TR)),
    )
    records[0].precision_level = 5
    await session.flush()

    listed = await repository.list_by_job(
        session,
        job_id=job.id,
        offset=0,
        limit=10,
        filters=SearchQueryFilters(language=SearchLanguage.EN),
        sort=SearchQuerySort(SearchQuerySortField.PRECISION_LEVEL, SortDirection.DESC),
    )

    assert [item.query_text for item in listed] == ["Query B"]
    assert (
        await repository.count_by_job(
            session,
            job_id=job.id,
            filters=SearchQueryFilters(),
        )
        == 2
    )
    assert await repository.find_existing_keys(
        session,
        job_id=job.id,
        keys={"query a", "missing"},
    ) == {"query a"}
    assert await repository.exists(session, records[0].id)


async def test_unique_key_updates_and_delete(session: AsyncSession) -> None:
    job = await create_job(session)
    repository = SearchQueryRepository()
    records = await repository.create_many(
        session,
        job_id=job.id,
        queries=(generated("Same"),),
    )
    await repository.update_status(session, query=records[0], status=SearchStatus.COMPLETED)
    await repository.update_result_count(session, query=records[0], result_count=4)

    assert records[0].status is SearchStatus.COMPLETED
    assert records[0].result_count == 4
    assert (
        await repository.get_by_id_for_job(
            session,
            records[0].id,
            job.id,
        )
        is records[0]
    )

    with pytest.raises(IntegrityError):
        await repository.create_many(
            session,
            job_id=job.id,
            queries=(generated("Same"),),
        )
    await session.rollback()


async def test_all_filters_empty_lookup_and_delete(session: AsyncSession) -> None:
    job = await create_job(session)
    repository = SearchQueryRepository()
    record = (
        await repository.create_many(
            session,
            job_id=job.id,
            queries=(generated("Filtered"),),
        )
    )[0]
    filters = SearchQueryFilters(
        source=SearchSource.GOOGLE_XRAY,
        status=SearchStatus.READY,
        query_type=QueryType.TITLE_LOCATION,
        precision_level=3,
    )

    assert (
        await repository.count_by_job(
            session,
            job_id=job.id,
            filters=filters,
        )
        == 1
    )
    assert (
        await repository.find_existing_keys(
            session,
            job_id=job.id,
            keys=(),
        )
        == set()
    )
    assert (
        await repository.list_by_keys(
            session,
            job_id=job.id,
            keys=(),
        )
        == []
    )
    await repository.delete(session, query=record)
    assert not await repository.exists(session, record.id)
