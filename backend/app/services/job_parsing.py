from collections.abc import Mapping
from uuid import UUID

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import JobStatus, RequirementType
from app.db.models import JobPosting
from app.domain.jobs import JobNotFoundError
from app.domain.jobs.parser_exceptions import (
    EmptyJobDescriptionError,
    JobParseStateError,
    JobParsingError,
    RequirementPersistenceError,
)
from app.domain.jobs.parser_types import JobParseInput, JobParseOutcome, ParsedJobData
from app.parsers.jobs.base import JobParser
from app.repositories.job_requirements import JobRequirementRepository
from app.repositories.jobs import JobRepository

logger = structlog.get_logger(__name__)
PARSEABLE_STATUSES = frozenset({JobStatus.DRAFT, JobStatus.PARSED})
UPDATED_JOB_FIELDS = (
    "description_clean",
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
)


class JobParsingService:
    def __init__(
        self,
        job_repository: JobRepository,
        requirement_repository: JobRequirementRepository,
        parser: JobParser,
    ) -> None:
        self.job_repository = job_repository
        self.requirement_repository = requirement_repository
        self.parser = parser

    async def parse_job(self, session: AsyncSession, job_id: UUID) -> JobParseOutcome:
        job = await self._get_job(session, job_id)
        self._validate_state(job)
        parsed = self._parse(job)
        self._validate_result(parsed)
        changes = self._job_changes(parsed)

        try:
            records = await self.requirement_repository.replace_for_job(
                session,
                job_id=job.id,
                requirements=parsed.requirements,
            )
            await self.job_repository.update(session, job=job, changes=changes)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.exception(
                "job_parse_failed",
                job_id=str(job_id),
                parser_version=self.parser.version,
            )
            raise RequirementPersistenceError(details={"job_id": str(job_id)}) from exc

        logger.info(
            "job_requirements_replaced",
            job_id=str(job_id),
            parser_version=parsed.parser_version,
            requirement_count=len(records),
        )
        if parsed.confidence < 0.4:
            logger.warning(
                "job_parse_low_confidence",
                job_id=str(job_id),
                parser_version=parsed.parser_version,
                confidence=parsed.confidence,
                warning_count=len(parsed.warnings),
            )
        return JobParseOutcome(
            job_id=job.id,
            status=job.status,
            parsed_data=parsed,
            created_requirement_count=len(records),
            updated_job_fields=UPDATED_JOB_FIELDS,
        )

    async def _get_job(self, session: AsyncSession, job_id: UUID) -> JobPosting:
        try:
            job = await self.job_repository.get_by_id(session, job_id)
        except SQLAlchemyError as exc:
            raise RequirementPersistenceError(details={"job_id": str(job_id)}) from exc
        if job is None:
            raise JobNotFoundError(details={"job_id": str(job_id)})
        return job

    @staticmethod
    def _validate_state(job: JobPosting) -> None:
        if job.status not in PARSEABLE_STATUSES:
            logger.warning(
                "job_parse_invalid_state",
                job_id=str(job.id),
                current_status=job.status.value,
            )
            raise JobParseStateError(
                details={"job_id": str(job.id), "current_status": job.status.value}
            )

    def _parse(self, job: JobPosting) -> ParsedJobData:
        try:
            return self.parser.parse(
                JobParseInput(
                    title=job.title,
                    description_raw=job.description_raw,
                    location_raw=job.location_raw,
                    city=job.city,
                    country=job.country,
                )
            )
        except EmptyJobDescriptionError:
            raise
        except (TypeError, ValueError) as exc:
            raise JobParsingError(details={"job_id": str(job.id)}) from exc

    @staticmethod
    def _validate_result(parsed: ParsedJobData) -> None:
        has_title = any(
            requirement.type is RequirementType.TITLE for requirement in parsed.requirements
        )
        if not has_title or not 0 <= parsed.confidence <= 1:
            raise JobParsingError("Parser returned an invalid result.")

    @staticmethod
    def _job_changes(parsed: ParsedJobData) -> Mapping[str, object]:
        education = [
            *(f"level:{value}" for value in parsed.education_levels),
            *(f"field:{value}" for value in parsed.education_fields),
        ]
        return {
            "description_clean": parsed.description_clean,
            "min_experience_years": parsed.min_experience_years,
            "max_experience_years": parsed.max_experience_years,
            "education_requirements": education,
            "required_skills": list(parsed.required_skills),
            "preferred_skills": list(parsed.preferred_skills),
            "languages": list(parsed.languages),
            "certifications": list(parsed.certifications),
            "keywords_tr": list(parsed.keywords_tr),
            "keywords_en": list(parsed.keywords_en),
            "status": JobStatus.PARSED,
        }
