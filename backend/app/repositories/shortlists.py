# mypy: disable-error-code="no-untyped-def,no-untyped-call"
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import CandidateSource, ShortlistStatus
from app.db.models import Candidate, CandidateMatch, ShortlistEntry
from app.repositories.base import BaseRepository


class ShortlistRepository(BaseRepository[ShortlistEntry]):
    def __init__(self) -> None:
        super().__init__(ShortlistEntry)

    def _options(self):
        return (selectinload(ShortlistEntry.candidate),)

    async def get_with_summary(
        self, session: AsyncSession, entry_id: UUID
    ) -> ShortlistEntry | None:
        statement = (
            select(ShortlistEntry).where(ShortlistEntry.id == entry_id).options(*self._options())
        )
        return (await session.scalars(statement)).one_or_none()

    async def get_by_job_candidate(
        self, session: AsyncSession, job_id: UUID, candidate_id: UUID
    ) -> ShortlistEntry | None:
        statement = (
            select(ShortlistEntry)
            .where(ShortlistEntry.job_id == job_id, ShortlistEntry.candidate_id == candidate_id)
            .options(*self._options())
        )
        return (await session.scalars(statement)).one_or_none()

    async def create(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        candidate_id: UUID,
        status: ShortlistStatus,
        recruiter_note: str | None,
    ) -> ShortlistEntry:
        entry = ShortlistEntry(
            job_id=job_id, candidate_id=candidate_id, status=status, recruiter_note=recruiter_note
        )
        session.add(entry)
        await session.flush()
        return entry

    async def update(
        self,
        session: AsyncSession,
        entry: ShortlistEntry,
        *,
        status: ShortlistStatus | None,
        recruiter_note: str | None,
        note_set: bool,
    ) -> ShortlistEntry:
        if status is not None:
            entry.status = status
        if note_set:
            entry.recruiter_note = recruiter_note
        await session.flush()
        return entry

    async def delete(self, session: AsyncSession, entry: ShortlistEntry) -> None:
        await session.delete(entry)
        await session.flush()

    async def list_by_job(
        self,
        session: AsyncSession,
        job_id: UUID,
        *,
        status: ShortlistStatus | None,
        min_match_score: float | None,
        city: str | None,
        source: CandidateSource | None,
        search: str | None,
        sort_by: str,
        descending: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[ShortlistEntry], int]:
        conditions = [ShortlistEntry.job_id == job_id]
        if status is not None:
            conditions.append(ShortlistEntry.status == status)
        if min_match_score is not None:
            conditions.append(CandidateMatch.total_score >= min_match_score)
        if city:
            conditions.append(func.lower(Candidate.city) == city.strip().casefold())
        if source is not None:
            conditions.append(Candidate.source == source)
        if search:
            term = search.strip().casefold()
            conditions.append(
                or_(
                    func.lower(Candidate.full_name).contains(term),
                    func.lower(Candidate.headline).contains(term),
                    func.lower(Candidate.current_title).contains(term),
                )
            )
        columns = {
            "created_at": ShortlistEntry.created_at,
            "updated_at": ShortlistEntry.updated_at,
            "match_score": CandidateMatch.total_score,
            "candidate_name": Candidate.full_name,
            "status": ShortlistEntry.status,
        }
        order = columns[sort_by].desc() if descending else columns[sort_by].asc()
        base = (
            select(ShortlistEntry)
            .join(Candidate)
            .outerjoin(
                CandidateMatch,
                (CandidateMatch.job_id == ShortlistEntry.job_id)
                & (CandidateMatch.candidate_id == ShortlistEntry.candidate_id),
            )
            .where(*conditions)
        )
        entries = list(
            (
                await session.scalars(
                    base.options(*self._options())
                    .order_by(order, ShortlistEntry.id.asc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        total = int(
            (
                await session.scalar(
                    select(func.count(ShortlistEntry.id))
                    .join(Candidate)
                    .outerjoin(
                        CandidateMatch,
                        (CandidateMatch.job_id == ShortlistEntry.job_id)
                        & (CandidateMatch.candidate_id == ShortlistEntry.candidate_id),
                    )
                    .where(*conditions)
                )
            )
            or 0
        )
        return entries, total

    async def match_for(
        self, session: AsyncSession, job_id: UUID, candidate_id: UUID
    ) -> CandidateMatch | None:
        statement = select(CandidateMatch).where(
            CandidateMatch.job_id == job_id, CandidateMatch.candidate_id == candidate_id
        )
        return (await session.scalars(statement)).one_or_none()

    async def matches_for_job(
        self, session: AsyncSession, job_id: UUID
    ) -> dict[UUID, CandidateMatch]:
        statement = select(CandidateMatch).where(CandidateMatch.job_id == job_id)
        return {record.candidate_id: record for record in (await session.scalars(statement)).all()}
