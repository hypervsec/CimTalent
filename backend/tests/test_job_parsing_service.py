from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import (
    JobSource,
    JobStatus,
    RequirementImportance,
    RequirementType,
)
from app.db.models import JobRequirement
from app.domain.jobs import JobNotFoundError
from app.domain.jobs.parser_exceptions import (
    EmptyJobDescriptionError,
    JobParseStateError,
    RequirementPersistenceError,
)
from app.domain.jobs.parser_types import ParsedRequirement
from app.parsers.jobs.rule_based import RuleBasedJobParser
from app.repositories.job_requirements import JobRequirementRepository
from app.repositories.jobs import JobRepository
from app.services.job_parsing import JobParsingService


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine: AsyncEngine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as database_session:
        yield database_session
    await engine.dispose()


def service(
    requirement_repository: JobRequirementRepository | None = None,
) -> JobParsingService:
    return JobParsingService(
        JobRepository(),
        requirement_repository or JobRequirementRepository(),
        RuleBasedJobParser(),
    )


async def create_job(
    session: AsyncSession,
    *,
    status: JobStatus = JobStatus.DRAFT,
    description: str = """
Requirements:
- Minimum 3 years of Python and PostgreSQL experience.
- Bachelor's degree in Computer Engineering.
- Fluent English.
Location:
- Remote
""",
) -> UUID:
    job = await JobRepository().create(
        session,
        data={
            "source": JobSource.MANUAL,
            "company_name": "Example",
            "title": "Backend Developer",
            "description_raw": description,
            "status": status,
        },
    )
    await session.commit()
    return job.id


async def test_parse_updates_summary_status_and_requirements(
    session: AsyncSession,
) -> None:
    job_id = await create_job(session)

    outcome = await service().parse_job(session, job_id)
    job = await JobRepository().get_by_id(session, job_id)
    assert job is not None

    assert outcome.status is JobStatus.PARSED
    assert outcome.created_requirement_count > 1
    assert job.status is JobStatus.PARSED
    assert job.description_clean is not None
    assert "python" in job.required_skills
    assert job.min_experience_years == 3
    assert "english:fluent" in job.languages
    assert any(
        item.type is RequirementType.TITLE
        for item in await JobRequirementRepository().list_by_job_id(session, job_id)
    )


async def test_reparse_is_idempotent_and_replaces_old_requirements(
    session: AsyncSession,
) -> None:
    job_id = await create_job(session)
    repository = JobRequirementRepository()
    parser_service = service(repository)
    first = await parser_service.parse_job(session, job_id)
    first_values = [
        (item.type, item.normalized_value, item.importance)
        for item in await repository.list_by_job_id(session, job_id)
    ]

    second = await parser_service.parse_job(session, job_id)
    second_values = [
        (item.type, item.normalized_value, item.importance)
        for item in await repository.list_by_job_id(session, job_id)
    ]

    assert second.created_requirement_count == first.created_requirement_count
    assert second_values == first_values
    assert len(second_values) == len(set(second_values))


async def test_missing_job_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(JobNotFoundError):
        await service().parse_job(session, uuid4())


@pytest.mark.parametrize(
    "job_status", [JobStatus.SOURCING, JobStatus.COMPLETED, JobStatus.ARCHIVED]
)
async def test_non_parseable_status_is_rejected(
    session: AsyncSession, job_status: JobStatus
) -> None:
    job_id = await create_job(session, status=job_status)

    with pytest.raises(JobParseStateError):
        await service().parse_job(session, job_id)


async def test_empty_description_is_rejected(session: AsyncSession) -> None:
    job_id = await create_job(session, description="   ")

    with pytest.raises(EmptyJobDescriptionError):
        await service().parse_job(session, job_id)


async def test_title_only_parse_returns_low_confidence_warning(
    session: AsyncSession,
) -> None:
    job_id = await create_job(session, description="General team information only.")

    outcome = await service().parse_job(session, job_id)

    assert outcome.parsed_data.confidence == 0.2
    assert "parser_low_confidence" in outcome.parsed_data.warnings
    assert "title_only_parse" in outcome.parsed_data.warnings


class FailingRequirementRepository(JobRequirementRepository):
    async def replace_for_job(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        requirements: tuple[ParsedRequirement, ...],
    ) -> list[JobRequirement]:
        await self.delete_by_job_id(session, job_id)
        raise SQLAlchemyError("simulated persistence failure")


async def test_persistence_failure_rolls_back_existing_state(
    session: AsyncSession,
) -> None:
    job_id = await create_job(session)
    repository = JobRequirementRepository()
    old = ParsedRequirement(
        type=RequirementType.SKILL,
        raw_value="Legacy",
        normalized_value="legacy",
        importance=RequirementImportance.REQUIRED,
        weight=1,
        confidence=1,
    )
    await repository.bulk_create(session, job_id=job_id, requirements=(old,))
    await session.commit()

    with pytest.raises(RequirementPersistenceError):
        await service(FailingRequirementRepository()).parse_job(session, job_id)

    job = await JobRepository().get_by_id(session, job_id)
    assert job is not None
    assert job.status is JobStatus.DRAFT
    assert [item.normalized_value for item in await repository.list_by_job_id(session, job_id)] == [
        "legacy"
    ]
