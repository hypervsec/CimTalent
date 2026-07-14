from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import JobSource, RequirementImportance, RequirementType
from app.domain.jobs.parser_types import ParsedRequirement
from app.repositories.job_requirements import JobRequirementRepository
from app.repositories.jobs import JobRepository


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: Any, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as database_session:
        yield database_session
    await engine.dispose()


def requirement(value: str) -> ParsedRequirement:
    return ParsedRequirement(
        type=RequirementType.SKILL,
        raw_value=value.title(),
        normalized_value=value,
        importance=RequirementImportance.REQUIRED,
        weight=1.0,
        confidence=0.95,
    )


async def test_replace_lists_and_counts_requirements(session: AsyncSession) -> None:
    job = await JobRepository().create(
        session,
        data={
            "source": JobSource.MANUAL,
            "company_name": "Example",
            "title": "Developer",
            "description_raw": "Python and SQL",
        },
    )
    repository = JobRequirementRepository()

    created = await repository.replace_for_job(
        session,
        job_id=job.id,
        requirements=(requirement("python"), requirement("sql")),
    )

    assert len(created) == 2
    assert await repository.count_by_job_id(session, job.id) == 2
    assert [item.normalized_value for item in await repository.list_by_job_id(session, job.id)] == [
        "python",
        "sql",
    ]

    await repository.replace_for_job(session, job_id=job.id, requirements=(requirement("docker"),))

    assert await repository.count_by_job_id(session, job.id) == 1
    assert [item.normalized_value for item in await repository.list_by_job_id(session, job.id)] == [
        "docker"
    ]


async def test_replace_with_empty_tuple_removes_existing(session: AsyncSession) -> None:
    job = await JobRepository().create(
        session,
        data={
            "source": JobSource.MANUAL,
            "company_name": "Example",
            "title": "Developer",
            "description_raw": "Python",
        },
    )
    repository = JobRequirementRepository()
    await repository.bulk_create(session, job_id=job.id, requirements=(requirement("python"),))

    assert await repository.replace_for_job(session, job_id=job.id, requirements=()) == []
    assert await repository.count_by_job_id(session, job.id) == 0
