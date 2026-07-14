from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import (
    JobSource,
    JobStatus,
    RequirementImportance,
    RequirementType,
    SearchLanguage,
)
from app.db.models import SearchQuery
from app.domain.jobs import JobNotFoundError
from app.domain.jobs.parser_types import ParsedRequirement
from app.domain.sourcing import (
    DuplicateSearchQueryError,
    JobNotParsedError,
    JobQueryGenerationStateError,
    SearchQueryPersistenceError,
)
from app.domain.sourcing.types import GeneratedQuery, SearchQueryFilters, SearchQuerySort
from app.repositories.job_requirements import JobRequirementRepository
from app.repositories.jobs import JobRepository
from app.repositories.search_queries import SearchQueryRepository
from app.services.query_generation import QueryGenerationService
from app.sourcing.query_generator import GoogleXRayQueryGenerator


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


def service(repository: SearchQueryRepository | None = None) -> QueryGenerationService:
    return QueryGenerationService(
        JobRepository(),
        JobRequirementRepository(),
        repository or SearchQueryRepository(),
        GoogleXRayQueryGenerator(),
    )


async def create_job(session: AsyncSession, status: JobStatus = JobStatus.PARSED) -> UUID:
    job = await JobRepository().create(
        session,
        data={
            "source": JobSource.MANUAL,
            "company_name": "Example",
            "title": "Backend Developer",
            "description_raw": "Python role",
            "city": "Bursa",
            "country": "Türkiye",
            "required_skills": ["Python", "SQL Server"],
            "status": status,
        },
    )
    if status is not JobStatus.DRAFT:
        await JobRequirementRepository().bulk_create(
            session,
            job_id=job.id,
            requirements=(
                ParsedRequirement(
                    RequirementType.TITLE,
                    "Backend Developer",
                    "software developer",
                    RequirementImportance.REQUIRED,
                    1,
                    1,
                ),
                ParsedRequirement(
                    RequirementType.SKILL,
                    "Python",
                    "Python",
                    RequirementImportance.REQUIRED,
                    1,
                    0.95,
                ),
            ),
        )
    await session.commit()
    return job.id


async def test_generation_is_idempotent_and_listed(session: AsyncSession) -> None:
    job_id = await create_job(session)
    query_service = service()

    first = await query_service.generate(
        session,
        job_id,
        max_queries=4,
        languages=(SearchLanguage.TR, SearchLanguage.EN),
        target_domain="linkedin.com/in",
    )
    second = await query_service.generate(
        session,
        job_id,
        max_queries=4,
        languages=(SearchLanguage.TR, SearchLanguage.EN),
        target_domain="linkedin.com/in",
    )
    listed = await query_service.list_for_job(
        session,
        job_id,
        page=1,
        page_size=20,
        filters=SearchQueryFilters(),
        sort=SearchQuerySort(),
    )

    assert first.created_count == 4
    assert second.created_count == 0
    assert second.existing_count == 4
    assert listed.total_items == 4
    assert len({item.normalized_query_key for item in listed.items}) == 4
    assert await query_service.get(session, first.queries[0].id) is not None


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (JobStatus.DRAFT, JobNotParsedError),
        (JobStatus.ARCHIVED, JobQueryGenerationStateError),
    ],
)
async def test_invalid_job_state_rejected(
    session: AsyncSession, status: JobStatus, error: type[Exception]
) -> None:
    job_id = await create_job(session, status)

    with pytest.raises(error):
        await service().generate(
            session,
            job_id,
            max_queries=10,
            languages=(SearchLanguage.EN,),
            target_domain="linkedin.com/in",
        )


async def test_missing_job_rejected(session: AsyncSession) -> None:
    with pytest.raises(JobNotFoundError):
        await service().generate(
            session,
            uuid4(),
            max_queries=10,
            languages=(SearchLanguage.EN,),
            target_domain="linkedin.com/in",
        )


class FailingRepository(SearchQueryRepository):
    async def create_many(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        queries: tuple[GeneratedQuery, ...],
    ) -> list[SearchQuery]:
        raise SQLAlchemyError("failure")


async def test_persistence_failure_rolls_back(session: AsyncSession) -> None:
    job_id = await create_job(session)

    with pytest.raises(SearchQueryPersistenceError):
        await service(FailingRepository()).generate(
            session,
            job_id,
            max_queries=2,
            languages=(SearchLanguage.EN,),
            target_domain="linkedin.com/in",
        )

    assert (
        await SearchQueryRepository().count_by_job(
            session, job_id=job_id, filters=SearchQueryFilters()
        )
        == 0
    )


class IntegrityFailingRepository(SearchQueryRepository):
    async def create_many(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        queries: tuple[GeneratedQuery, ...],
    ) -> list[SearchQuery]:
        from sqlalchemy.exc import IntegrityError

        raise IntegrityError("statement", {}, Exception("duplicate"))


async def test_integrity_and_missing_list(session: AsyncSession) -> None:
    job_id = await create_job(session)
    with pytest.raises(DuplicateSearchQueryError):
        await service(IntegrityFailingRepository()).generate(
            session,
            job_id,
            max_queries=2,
            languages=(SearchLanguage.EN,),
            target_domain="linkedin.com/in",
        )
    with pytest.raises(JobNotFoundError):
        await service().list_for_job(
            session,
            uuid4(),
            page=1,
            page_size=10,
            filters=SearchQueryFilters(),
            sort=SearchQuerySort(),
        )
