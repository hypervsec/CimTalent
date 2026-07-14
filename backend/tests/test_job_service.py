from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import JobSource, JobStatus
from app.domain.jobs import (
    DuplicateJobError,
    InvalidJobStatusTransitionError,
    JobListFilters,
    JobNotFoundError,
    JobSort,
    JobValidationError,
)
from app.repositories.jobs import JobRepository
from app.services.jobs import JobService


@pytest.fixture
async def service_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def service() -> JobService:
    return JobService(JobRepository())


def create_data(**changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "source": JobSource.MANUAL,
        "company_name": "Example Company",
        "title": "Backend Developer",
        "description_raw": "Build Python APIs",
    }
    data.update(changes)
    return data


async def test_create_get_list_and_delete_job(
    service_session: AsyncSession, service: JobService
) -> None:
    created = await service.create_job(service_session, data=create_data())

    assert (await service.get_job(service_session, created.job.id)).job is created.job
    page = await service.list_jobs(
        service_session,
        page=1,
        page_size=20,
        filters=JobListFilters(),
        sort=JobSort(),
    )
    assert page.total_items == 1
    assert page.total_pages == 1
    assert page.has_next is False

    await service.delete_job(service_session, created.job.id)
    with pytest.raises(JobNotFoundError):
        await service.get_job(service_session, created.job.id)


async def test_duplicate_job_is_rejected(
    service_session: AsyncSession, service: JobService
) -> None:
    await service.create_job(service_session, data=create_data())

    with pytest.raises(DuplicateJobError):
        await service.create_job(
            service_session,
            data=create_data(company_name=" example company ", title="BACKEND DEVELOPER"),
        )


@pytest.mark.parametrize("operation", ["get", "update", "delete", "requirements"])
async def test_missing_job_raises(
    service_session: AsyncSession, service: JobService, operation: str
) -> None:
    job_id = uuid4()

    with pytest.raises(JobNotFoundError):
        if operation == "get":
            await service.get_job(service_session, job_id)
        elif operation == "update":
            await service.update_job(service_session, job_id, changes={"title": "New"})
        elif operation == "delete":
            await service.delete_job(service_session, job_id)
        else:
            await service.get_job_requirements(service_session, job_id)


async def test_valid_and_invalid_status_transitions(
    service_session: AsyncSession, service: JobService
) -> None:
    created = await service.create_job(service_session, data=create_data())

    updated = await service.update_job(
        service_session, created.job.id, changes={"status": JobStatus.PARSED}
    )
    assert updated.job.status is JobStatus.PARSED

    with pytest.raises(InvalidJobStatusTransitionError):
        await service.update_job(
            service_session, created.job.id, changes={"status": JobStatus.COMPLETED}
        )


async def test_update_experience_range_uses_existing_value(
    service_session: AsyncSession, service: JobService
) -> None:
    created = await service.create_job(
        service_session,
        data=create_data(min_experience_years=2.0, max_experience_years=5.0),
    )

    with pytest.raises(JobValidationError):
        await service.update_job(
            service_session,
            created.job.id,
            changes={"min_experience_years": 6.0},
        )


async def test_update_source_requires_url(
    service_session: AsyncSession, service: JobService
) -> None:
    created = await service.create_job(service_session, data=create_data())

    with pytest.raises(JobValidationError):
        await service.update_job(
            service_session, created.job.id, changes={"source": JobSource.LINKEDIN}
        )


async def test_empty_update_is_noop_and_requirements_are_empty(
    service_session: AsyncSession, service: JobService
) -> None:
    created = await service.create_job(service_session, data=create_data())

    unchanged = await service.update_job(service_session, created.job.id, changes={})

    assert unchanged.job.title == created.job.title
    assert await service.get_job_requirements(service_session, created.job.id) == []
