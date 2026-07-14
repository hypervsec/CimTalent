# mypy: disable-error-code="no-untyped-def"
import csv
from io import StringIO
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ShortlistStatus
from app.domain.candidates import CandidateNotFoundError
from app.domain.jobs import JobNotFoundError
from app.domain.jobs.exceptions import JobPersistenceError
from app.domain.shortlists import (
    ALLOWED_TRANSITIONS,
    InvalidShortlistStatusTransitionError,
    ShortlistNotFoundError,
)
from app.repositories.candidate_matches import CandidateMatchRepository
from app.repositories.shortlists import ShortlistRepository


class ShortlistService:
    def __init__(
        self, repository: ShortlistRepository, match_repository: CandidateMatchRepository
    ) -> None:
        self.repository = repository
        self.match_repository = match_repository

    async def add_or_update_shortlist(
        self,
        session: AsyncSession,
        job_id: UUID,
        candidate_id: UUID,
        status: ShortlistStatus,
        recruiter_note: str | None,
    ):
        job = await self.match_repository.job_with_requirements(session, job_id)
        if job is None:
            raise JobNotFoundError(details={"job_id": str(job_id)})
        candidate = await self.match_repository.candidate_with_profile(session, candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(details={"candidate_id": str(candidate_id)})
        entry = await self.repository.get_by_job_candidate(session, job_id, candidate_id)
        try:
            if entry is None:
                entry = await self.repository.create(
                    session,
                    job_id=job_id,
                    candidate_id=candidate_id,
                    status=status,
                    recruiter_note=recruiter_note,
                )
            else:
                self._validate_transition(entry.status, status)
                entry = await self.repository.update(
                    session, entry, status=status, recruiter_note=recruiter_note, note_set=True
                )
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            raise JobPersistenceError(details={"job_id": str(job_id)}) from exc
        return await self.get_shortlist_entry(session, entry.id)

    async def get_shortlist_entry(self, session: AsyncSession, entry_id: UUID):
        entry = await self.repository.get_with_summary(session, entry_id)
        if entry is None:
            raise ShortlistNotFoundError(details={"shortlist_id": str(entry_id)})
        return entry

    async def list_job_shortlist(self, session: AsyncSession, job_id: UUID, **filters: object):
        if await self.match_repository.job_with_requirements(session, job_id) is None:
            raise JobNotFoundError(details={"job_id": str(job_id)})
        return await self.repository.list_by_job(session, job_id, **filters)  # type: ignore[arg-type]

    async def update_shortlist_entry(
        self,
        session: AsyncSession,
        entry_id: UUID,
        *,
        status: ShortlistStatus | None,
        recruiter_note: str | None,
        note_set: bool,
    ):
        entry = await self.get_shortlist_entry(session, entry_id)
        if status is not None:
            self._validate_transition(entry.status, status)
        try:
            await self.repository.update(
                session, entry, status=status, recruiter_note=recruiter_note, note_set=note_set
            )
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            raise JobPersistenceError(details={"shortlist_id": str(entry_id)}) from exc
        return await self.get_shortlist_entry(session, entry_id)

    async def delete_shortlist_entry(self, session: AsyncSession, entry_id: UUID) -> None:
        entry = await self.get_shortlist_entry(session, entry_id)
        try:
            await self.repository.delete(session, entry)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            raise JobPersistenceError(details={"shortlist_id": str(entry_id)}) from exc

    async def export_job_shortlist_csv(self, session: AsyncSession, job_id: UUID) -> str:
        entries, _ = await self.list_job_shortlist(
            session,
            job_id,
            status=None,
            min_match_score=None,
            city=None,
            source=None,
            search=None,
            sort_by="created_at",
            descending=False,
            offset=0,
            limit=10_000,
        )
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "candidate_name",
                "headline",
                "current_title",
                "current_company",
                "city",
                "country",
                "profile_url",
                "match_score",
                "shortlist_status",
                "recruiter_note",
                "created_at",
                "updated_at",
            ]
        )
        matches = await self.repository.matches_for_job(session, job_id)
        for entry in entries:
            candidate = entry.candidate
            match = matches.get(entry.candidate_id)
            writer.writerow(
                [
                    self._safe(candidate.full_name),
                    self._safe(candidate.headline),
                    self._safe(candidate.current_title),
                    self._safe(candidate.current_company),
                    self._safe(candidate.city),
                    self._safe(candidate.country),
                    self._safe(candidate.primary_profile_url),
                    match.total_score if match else "",
                    entry.status.value,
                    self._safe(entry.recruiter_note),
                    entry.created_at.isoformat(),
                    entry.updated_at.isoformat(),
                ]
            )
        return "\ufeff" + output.getvalue()

    @staticmethod
    def _validate_transition(current: ShortlistStatus, next_status: ShortlistStatus) -> None:
        if current is not next_status and next_status not in ALLOWED_TRANSITIONS[current]:
            raise InvalidShortlistStatusTransitionError(
                details={"from": current.value, "to": next_status.value}
            )

    @staticmethod
    def _safe(value: object) -> str:
        text = "" if value is None else str(value)
        return "'" + text if text.startswith(("=", "+", "-", "@")) else text
