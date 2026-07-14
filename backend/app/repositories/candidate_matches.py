from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import CandidateProfileStatus, CandidateSource
from app.db.models import Candidate, CandidateMatch, JobPosting, SearchQuery, SearchResult
from app.repositories.base import BaseRepository


class CandidateMatchRepository(BaseRepository[CandidateMatch]):
    def __init__(self) -> None:
        super().__init__(CandidateMatch)

    async def get_with_profile(
        self, session: AsyncSession, match_id: UUID
    ) -> CandidateMatch | None:
        statement = (
            select(CandidateMatch)
            .where(CandidateMatch.id == match_id)
            .options(selectinload(CandidateMatch.candidate), selectinload(CandidateMatch.job))
        )
        return (await session.scalars(statement)).one_or_none()

    async def get_for_pair(
        self, session: AsyncSession, job_id: UUID, candidate_id: UUID
    ) -> CandidateMatch | None:
        statement = select(CandidateMatch).where(
            CandidateMatch.job_id == job_id, CandidateMatch.candidate_id == candidate_id
        )
        return (await session.scalars(statement)).one_or_none()

    async def upsert(
        self, session: AsyncSession, *, job_id: UUID, candidate_id: UUID, data: dict[str, object]
    ) -> CandidateMatch:
        record = await self.get_for_pair(session, job_id, candidate_id)
        if record is None:
            record = CandidateMatch(job_id=job_id, candidate_id=candidate_id, **data)
            session.add(record)
        else:
            for key, value in data.items():
                setattr(record, key, value)
        await session.flush()
        return record

    async def list_for_job(
        self,
        session: AsyncSession,
        job_id: UUID,
        *,
        min_score: float | None,
        max_score: float | None,
        city: str | None,
        source: CandidateSource | None,
        profile_status: CandidateProfileStatus | None,
        sort_by: str,
        descending: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[CandidateMatch], int]:
        conditions = [CandidateMatch.job_id == job_id]
        if min_score is not None:
            conditions.append(CandidateMatch.total_score >= min_score)
        if max_score is not None:
            conditions.append(CandidateMatch.total_score <= max_score)
        if city:
            conditions.append(func.lower(Candidate.city) == city.strip().casefold())
        if source is not None:
            conditions.append(Candidate.source == source)
        if profile_status is not None:
            conditions.append(Candidate.profile_status == profile_status)
        columns = {
            "total_score": CandidateMatch.total_score,
            "created_at": CandidateMatch.created_at,
            "data_quality_score": Candidate.data_quality_score,
        }
        order = columns[sort_by].desc() if descending else columns[sort_by].asc()
        statement = (
            select(CandidateMatch)
            .join(CandidateMatch.candidate)
            .where(*conditions)
            .options(selectinload(CandidateMatch.candidate))
            .order_by(order, CandidateMatch.id.asc())
            .offset(offset)
            .limit(limit)
        )
        records = list((await session.scalars(statement)).all())
        total = int(
            (
                await session.scalar(
                    select(func.count(CandidateMatch.id))
                    .join(CandidateMatch.candidate)
                    .where(*conditions)
                )
            )
            or 0
        )
        return records, total

    async def candidates_for_job(
        self, session: AsyncSession, job_id: UUID, candidate_ids: Sequence[UUID] | None = None
    ) -> list[Candidate]:
        statement = select(Candidate).options(
            selectinload(Candidate.experiences),
            selectinload(Candidate.skills),
            selectinload(Candidate.educations),
            selectinload(Candidate.languages),
            selectinload(Candidate.certifications),
        )
        if candidate_ids:
            statement = statement.where(Candidate.id.in_(candidate_ids))
        else:
            linked = (
                select(SearchResult.candidate_id)
                .join(SearchQuery)
                .where(SearchQuery.job_id == job_id, SearchResult.candidate_id.is_not(None))
            )
            statement = statement.where(Candidate.id.in_(linked))
        return list((await session.scalars(statement)).unique().all())

    async def candidate_with_profile(
        self, session: AsyncSession, candidate_id: UUID
    ) -> Candidate | None:
        statement = (
            select(Candidate)
            .where(Candidate.id == candidate_id)
            .options(
                selectinload(Candidate.experiences),
                selectinload(Candidate.skills),
                selectinload(Candidate.educations),
                selectinload(Candidate.languages),
                selectinload(Candidate.certifications),
            )
        )
        return (await session.scalars(statement)).unique().one_or_none()

    async def job_with_requirements(self, session: AsyncSession, job_id: UUID) -> JobPosting | None:
        statement = (
            select(JobPosting)
            .where(JobPosting.id == job_id)
            .options(selectinload(JobPosting.requirements))
        )
        return (await session.scalars(statement)).unique().one_or_none()
