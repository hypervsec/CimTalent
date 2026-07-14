from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import JobSource, JobStatus
from app.db.models import JobPosting, JobRequirement
from app.domain.jobs import (
    DuplicateJobError,
    InvalidJobStatusTransitionError,
    JobConflictError,
    JobListFilters,
    JobNotFoundError,
    JobPersistenceError,
    JobSort,
    JobValidationError,
    JobWithCounts,
    PagedJobs,
)
from app.domain.jobs.normalization import normalize_duplicate_text, normalize_source_url
from app.repositories.jobs import JobRepository

ALLOWED_STATUS_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.DRAFT: frozenset({JobStatus.PARSED, JobStatus.ARCHIVED}),
    JobStatus.PARSED: frozenset({JobStatus.SOURCING, JobStatus.ARCHIVED, JobStatus.DRAFT}),
    JobStatus.SOURCING: frozenset({JobStatus.COMPLETED, JobStatus.ARCHIVED, JobStatus.PARSED}),
    JobStatus.COMPLETED: frozenset({JobStatus.ARCHIVED, JobStatus.SOURCING}),
    JobStatus.ARCHIVED: frozenset({JobStatus.DRAFT}),
}

UPDATE_FIELDS = frozenset(
    {
        "source",
        "source_url",
        "company_name",
        "title",
        "description_raw",
        "description_clean",
        "location_raw",
        "city",
        "country",
        "employment_type",
        "seniority_level",
        "min_experience_years",
        "max_experience_years",
        "education_requirements",
        "required_skills",
        "preferred_skills",
        "languages",
        "certifications",
        "keywords_tr",
        "keywords_en",
        "status",
    }
)


class JobService:
    def __init__(self, repository: JobRepository) -> None:
        self.repository = repository

    async def create_job(
        self, session: AsyncSession, *, data: Mapping[str, object]
    ) -> JobWithCounts:
        prepared = dict(data)
        source = self._require_source(prepared.get("source", JobSource.MANUAL))
        source_url = self._optional_string(prepared.get("source_url"), "source_url")
        normalized_url = normalize_source_url(source_url)
        prepared["source"] = source
        prepared["source_url"] = normalized_url
        self._validate_source_url(source, normalized_url)
        self._validate_experience(
            self._optional_float(prepared.get("min_experience_years"), "min_experience_years"),
            self._optional_float(prepared.get("max_experience_years"), "max_experience_years"),
        )
        await self._reject_duplicate(session, prepared)

        try:
            job = await self.repository.create(session, data=prepared)
            await session.commit()
            record = await self.repository.get_by_id_with_counts(session, job.id)
        except IntegrityError as exc:
            await session.rollback()
            raise JobConflictError() from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            raise JobPersistenceError() from exc
        if record is None:
            raise JobPersistenceError("Created job could not be reloaded.")
        return record

    async def get_job(self, session: AsyncSession, job_id: UUID) -> JobWithCounts:
        try:
            record = await self.repository.get_by_id_with_counts(session, job_id)
        except SQLAlchemyError as exc:
            raise JobPersistenceError() from exc
        if record is None:
            raise JobNotFoundError(details={"job_id": str(job_id)})
        return record

    async def list_jobs(
        self,
        session: AsyncSession,
        *,
        page: int,
        page_size: int,
        filters: JobListFilters,
        sort: JobSort,
    ) -> PagedJobs:
        offset = (page - 1) * page_size
        try:
            items = await self.repository.list(
                session,
                offset=offset,
                limit=page_size,
                filters=filters,
                sort=sort,
            )
            total_items = await self.repository.count(session, filters=filters)
        except SQLAlchemyError as exc:
            raise JobPersistenceError() from exc
        return PagedJobs(
            items=items,
            page=page,
            page_size=page_size,
            total_items=total_items,
        )

    async def update_job(
        self,
        session: AsyncSession,
        job_id: UUID,
        *,
        changes: Mapping[str, object],
    ) -> JobWithCounts:
        job = await self._get_job_entity(session, job_id)
        prepared = dict(changes)
        unknown_fields = prepared.keys() - UPDATE_FIELDS
        if unknown_fields:
            raise JobValidationError(
                "Unknown update fields.", details={"fields": sorted(unknown_fields)}
            )
        if not prepared:
            return await self.get_job(session, job_id)

        source = self._require_source(prepared.get("source", job.source))
        source_url = self._optional_string(prepared.get("source_url", job.source_url), "source_url")
        normalized_url = normalize_source_url(source_url)
        if "source_url" in prepared:
            prepared["source_url"] = normalized_url
        self._validate_source_url(source, normalized_url)

        minimum = self._optional_float(
            prepared.get("min_experience_years", job.min_experience_years),
            "min_experience_years",
        )
        maximum = self._optional_float(
            prepared.get("max_experience_years", job.max_experience_years),
            "max_experience_years",
        )
        self._validate_experience(minimum, maximum)

        if "status" in prepared:
            new_status = self._require_status(prepared["status"])
            self._validate_status_transition(job.status, new_status)
            prepared["status"] = new_status

        duplicate_data: dict[str, object] = {
            "company_name": prepared.get("company_name", job.company_name),
            "title": prepared.get("title", job.title),
            "source": source,
            "source_url": normalized_url,
            "description_raw": prepared.get("description_raw", job.description_raw),
        }
        await self._reject_duplicate(session, duplicate_data, exclude_id=job.id)

        try:
            await self.repository.update(session, job=job, changes=prepared)
            await session.commit()
            record = await self.repository.get_by_id_with_counts(session, job.id)
        except IntegrityError as exc:
            await session.rollback()
            raise JobConflictError() from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            raise JobPersistenceError() from exc
        if record is None:
            raise JobPersistenceError("Updated job could not be reloaded.")
        return record

    async def delete_job(self, session: AsyncSession, job_id: UUID) -> None:
        job = await self._get_job_entity(session, job_id)
        try:
            await self.repository.delete(session, job=job)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise JobConflictError("Job posting could not be deleted.") from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            raise JobPersistenceError() from exc

    async def get_job_requirements(
        self, session: AsyncSession, job_id: UUID
    ) -> list[JobRequirement]:
        try:
            if not await self.repository.exists(session, job_id):
                raise JobNotFoundError(details={"job_id": str(job_id)})
            return await self.repository.list_requirements(session, job_id)
        except SQLAlchemyError as exc:
            raise JobPersistenceError() from exc

    async def _get_job_entity(self, session: AsyncSession, job_id: UUID) -> JobPosting:
        try:
            job = await self.repository.get_by_id(session, job_id)
        except SQLAlchemyError as exc:
            raise JobPersistenceError() from exc
        if job is None:
            raise JobNotFoundError(details={"job_id": str(job_id)})
        return job

    async def _reject_duplicate(
        self,
        session: AsyncSession,
        data: Mapping[str, object],
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        company_name = self._require_string(data.get("company_name"), "company_name")
        title = self._require_string(data.get("title"), "title")
        description = self._require_string(data.get("description_raw"), "description_raw")
        source = self._require_source(data.get("source"))
        source_url = self._optional_string(data.get("source_url"), "source_url")
        try:
            duplicate = await self.repository.find_duplicate(
                session,
                company_name=normalize_duplicate_text(company_name),
                title=normalize_duplicate_text(title),
                source=source,
                source_url=normalize_source_url(source_url),
                description_raw=normalize_duplicate_text(description),
                exclude_id=exclude_id,
            )
        except SQLAlchemyError as exc:
            raise JobPersistenceError() from exc
        if duplicate is not None:
            raise DuplicateJobError(details={"existing_job_id": str(duplicate.id)})

    @staticmethod
    def _validate_status_transition(current: JobStatus, target: JobStatus) -> None:
        if current is target:
            return
        if target not in ALLOWED_STATUS_TRANSITIONS[current]:
            raise InvalidJobStatusTransitionError(
                details={"from": current.value, "to": target.value}
            )

    @staticmethod
    def _validate_source_url(source: JobSource, source_url: str | None) -> None:
        if source is not JobSource.MANUAL and source_url is None:
            raise JobValidationError("source_url is required for non-manual job sources.")

    @staticmethod
    def _validate_experience(minimum: float | None, maximum: float | None) -> None:
        if minimum is not None and minimum < 0:
            raise JobValidationError("min_experience_years cannot be negative.")
        if maximum is not None and maximum < 0:
            raise JobValidationError("max_experience_years cannot be negative.")
        if minimum is not None and maximum is not None and maximum < minimum:
            raise JobValidationError(
                "max_experience_years cannot be lower than min_experience_years."
            )

    @staticmethod
    def _require_source(value: object) -> JobSource:
        if not isinstance(value, JobSource):
            raise JobValidationError("source must be a JobSource value.")
        return value

    @staticmethod
    def _require_status(value: object) -> JobStatus:
        if not isinstance(value, JobStatus):
            raise JobValidationError("status must be a JobStatus value.")
        return value

    @staticmethod
    def _require_string(value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise JobValidationError(f"{field_name} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _optional_string(value: object, field_name: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise JobValidationError(f"{field_name} must be a string or null.")
        return value.strip() or None

    @staticmethod
    def _optional_float(value: object, field_name: str) -> float | None:
        if value is None:
            return None
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise JobValidationError(f"{field_name} must be numeric or null.")
        return float(value)
