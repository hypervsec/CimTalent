from collections.abc import Sequence
from typing import cast
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import JobStatus
from app.db.models import CandidateMatch
from app.domain.candidates import CandidateNotFoundError
from app.domain.jobs import JobNotFoundError, MatchNotFoundError
from app.domain.jobs.exceptions import JobConflictError, JobPersistenceError
from app.domain.matching.engine import RuleBasedMatchingEngine
from app.repositories.candidate_matches import CandidateMatchRepository


class CandidateMatchingService:
    def __init__(
        self, repository: CandidateMatchRepository, engine: RuleBasedMatchingEngine
    ) -> None:
        self.repository = repository
        self.engine = engine

    async def calculate_match(
        self, session: AsyncSession, job_id: UUID, candidate_id: UUID
    ) -> CandidateMatch:
        job = await self._job(session, job_id)
        candidate = await self.repository.candidate_with_profile(session, candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(details={"candidate_id": str(candidate_id)})
        score = self.engine.calculate(job, candidate)
        data = {
            "total_score": score.scores["total"],
            "title_score": score.scores["title"],
            "skill_score": score.scores["skill"],
            "experience_score": score.scores["experience"],
            "industry_score": score.scores["industry"],
            "education_score": score.scores["education"],
            "location_score": score.scores["location"],
            "language_score": score.scores["language"],
            "certification_score": score.scores["certification"],
            "semantic_score": None,
            "matched_requirements": score.matched,
            "missing_requirements": score.missing,
            "uncertain_requirements": score.uncertain,
            "explanation": score.explanation,
            "score_version": self.engine.version,
        }
        try:
            record = await self.repository.upsert(
                session,
                job_id=job.id,
                candidate_id=candidate.id,
                data=cast(dict[str, object], data),
            )
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            raise JobPersistenceError(details={"job_id": str(job_id)}) from exc
        hydrated = await self.repository.get_with_profile(session, record.id)
        if hydrated is None:
            raise JobPersistenceError(details={"job_id": str(job_id)})
        return hydrated

    async def calculate_all_matches(
        self, session: AsyncSession, job_id: UUID, candidate_ids: Sequence[UUID] | None = None
    ) -> list[CandidateMatch]:
        await self._job(session, job_id)
        candidates = await self.repository.candidates_for_job(session, job_id, candidate_ids)
        return [
            await self.calculate_match(session, job_id, candidate.id) for candidate in candidates
        ]

    async def get_match(self, session: AsyncSession, match_id: UUID) -> CandidateMatch:
        record = await self.repository.get_with_profile(session, match_id)
        if record is None:
            raise MatchNotFoundError(details={"match_id": str(match_id)})
        return record

    async def list_job_matches(
        self, session: AsyncSession, job_id: UUID, **filters: object
    ) -> tuple[list[CandidateMatch], int]:
        await self._job(session, job_id)
        return await self.repository.list_for_job(session, job_id, **filters)  # type: ignore[arg-type]

    async def recalculate_match(self, session: AsyncSession, match_id: UUID) -> CandidateMatch:
        record = await self.get_match(session, match_id)
        return await self.calculate_match(session, record.job_id, record.candidate_id)

    async def _job(self, session: AsyncSession, job_id: UUID):  # type: ignore[no-untyped-def]
        job = await self.repository.job_with_requirements(session, job_id)
        if job is None:
            raise JobNotFoundError(details={"job_id": str(job_id)})
        if job.status is not JobStatus.PARSED:
            raise JobConflictError(
                "Job must be parsed before matching.", details={"job_id": str(job_id)}
            )
        return job
