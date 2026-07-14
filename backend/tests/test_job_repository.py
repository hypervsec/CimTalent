from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import (
    CandidateSource,
    JobSource,
    JobStatus,
    RequirementImportance,
    RequirementSource,
    RequirementType,
    SearchLanguage,
    SearchSource,
)
from app.db.models import (
    Candidate,
    CandidateMatch,
    JobRequirement,
    SearchQuery,
    ShortlistEntry,
)
from app.domain.jobs import JobListFilters, JobSort, JobSortField, SortDirection
from app.repositories.jobs import JobRepository


@pytest.fixture
async def async_engine() -> AsyncIterator[AsyncEngine]:
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
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session(async_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as database_session:
        yield database_session
        await database_session.rollback()


@pytest.fixture
def repository() -> JobRepository:
    return JobRepository()


def job_data(
    company: str = "Example Company",
    title: str = "Backend Developer",
    **changes: object,
) -> dict[str, object]:
    data: dict[str, object] = {
        "source": JobSource.MANUAL,
        "company_name": company,
        "title": title,
        "description_raw": "Build Python APIs",
        "city": "Bursa",
    }
    data.update(changes)
    return data


async def test_create_get_exists_update_and_delete(
    session: AsyncSession, repository: JobRepository
) -> None:
    job = await repository.create(session, data=job_data())

    assert await repository.get_by_id(session, job.id) is job
    assert await repository.exists(session, job.id) is True

    await repository.update(session, job=job, changes={"title": "Senior Developer"})
    assert job.title == "Senior Developer"

    await repository.delete(session, job=job)
    assert await repository.get_by_id(session, job.id) is None


async def test_missing_job_returns_none(session: AsyncSession, repository: JobRepository) -> None:
    from uuid import uuid4

    assert await repository.get_by_id(session, uuid4()) is None


async def test_list_paginates_and_sorts(session: AsyncSession, repository: JobRepository) -> None:
    for company in ("Charlie", "Alpha", "Bravo"):
        await repository.create(session, data=job_data(company=company))

    ascending = await repository.list(
        session,
        offset=0,
        limit=2,
        filters=JobListFilters(),
        sort=JobSort(JobSortField.COMPANY_NAME, SortDirection.ASC),
    )
    descending = await repository.list(
        session,
        offset=0,
        limit=3,
        filters=JobListFilters(),
        sort=JobSort(JobSortField.COMPANY_NAME, SortDirection.DESC),
    )

    assert [record.job.company_name for record in ascending] == ["Alpha", "Bravo"]
    assert [record.job.company_name for record in descending] == [
        "Charlie",
        "Bravo",
        "Alpha",
    ]


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        (JobListFilters(status=JobStatus.DRAFT), 2),
        (JobListFilters(source=JobSource.LINKEDIN), 1),
        (JobListFilters(city=" bursa "), 1),
        (JobListFilters(search="backend"), 1),
        (JobListFilters(search="Acme"), 1),
        (JobListFilters(search="welding"), 1),
    ],
)
async def test_count_and_filters(
    session: AsyncSession,
    repository: JobRepository,
    filters: JobListFilters,
    expected: int,
) -> None:
    await repository.create(session, data=job_data(company="Acme", city="Bursa"))
    await repository.create(
        session,
        data=job_data(
            company="Industry",
            title="Welding Engineer",
            source=JobSource.LINKEDIN,
            source_url="https://example.test/jobs/1",
            city="Istanbul",
            description_raw="Welding systems",
        ),
    )

    assert await repository.count(session, filters=filters) == expected


async def test_search_escapes_sql_wildcards(
    session: AsyncSession, repository: JobRepository
) -> None:
    await repository.create(session, data=job_data())

    assert await repository.count(session, filters=JobListFilters(search="%")) == 0


async def test_counts_and_requirements_are_returned_without_n_plus_one(
    session: AsyncSession,
    repository: JobRepository,
    async_engine: AsyncEngine,
) -> None:
    job = await repository.create(session, data=job_data())
    candidate = Candidate(source=CandidateSource.DEMO, full_name="Demo Candidate")
    requirement = JobRequirement(
        job=job,
        type=RequirementType.SKILL,
        raw_value="Python",
        normalized_value="python",
        importance=RequirementImportance.REQUIRED,
        source=RequirementSource.MANUAL,
    )
    query = SearchQuery(
        job=job,
        source=SearchSource.MANUAL,
        language=SearchLanguage.EN,
        query_text="Python developer",
        normalized_query_key="python developer",
    )
    match = CandidateMatch(
        job=job,
        candidate=candidate,
        total_score=80,
        title_score=80,
        skill_score=80,
        experience_score=80,
        industry_score=80,
        education_score=80,
        location_score=80,
        language_score=80,
        certification_score=80,
        score_version="v1",
    )
    shortlist = ShortlistEntry(job=job, candidate=candidate)
    session.add_all([requirement, query, match, shortlist])
    await session.flush()

    statements = 0

    def count_statement(*_: object) -> None:
        nonlocal statements
        statements += 1

    event.listen(async_engine.sync_engine, "before_cursor_execute", count_statement)
    try:
        records = await repository.list(
            session,
            offset=0,
            limit=20,
            filters=JobListFilters(),
            sort=JobSort(),
        )
    finally:
        event.remove(async_engine.sync_engine, "before_cursor_execute", count_statement)

    assert statements == 1
    assert records[0].requirement_count == 1
    assert records[0].search_query_count == 1
    assert records[0].candidate_match_count == 1
    assert records[0].shortlist_count == 1
    requirements = await repository.list_requirements(session, job.id)
    assert [item.normalized_value for item in requirements] == ["python"]
