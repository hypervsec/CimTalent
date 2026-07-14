from collections.abc import Collection, Mapping
from typing import TypeVar, cast
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Candidate,
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateLanguage,
    CandidateSkill,
)

Child = TypeVar(
    "Child",
    CandidateExperience,
    CandidateEducation,
    CandidateSkill,
    CandidateCertification,
    CandidateLanguage,
)


class CandidateEnrichmentRepository:
    async def load_candidate_profile(
        self, session: AsyncSession, candidate_id: UUID
    ) -> Candidate | None:
        return cast(
            Candidate | None,
            await session.scalar(
                select(Candidate)
                .where(Candidate.id == candidate_id)
                .execution_options(populate_existing=True)
                .options(
                    selectinload(Candidate.experiences),
                    selectinload(Candidate.educations),
                    selectinload(Candidate.skills),
                    selectinload(Candidate.certifications),
                    selectinload(Candidate.languages),
                    selectinload(Candidate.enrichment_runs),
                )
            ),
        )

    async def create(
        self, session: AsyncSession, model: type[Child], data: Mapping[str, object]
    ) -> Child:
        record = model(**dict(data))
        session.add(record)
        await session.flush()
        return record

    async def update(
        self, session: AsyncSession, record: Child, changes: Mapping[str, object]
    ) -> Child:
        for name, value in changes.items():
            setattr(record, name, value)
        await session.flush()
        return record

    async def delete_records(self, session: AsyncSession, records: Collection[Child]) -> int:
        for record in records:
            await session.delete(record)
        await session.flush()
        return len(records)

    async def replace_section(
        self,
        session: AsyncSession,
        *,
        model: type[Child],
        candidate_id: UUID,
        rows: Collection[Mapping[str, object]],
    ) -> list[Child]:
        await session.execute(delete(model).where(model.candidate_id == candidate_id))
        created = [model(**dict(row)) for row in rows]
        session.add_all(created)
        await session.flush()
        return created

    async def flush(self, session: AsyncSession) -> None:
        await session.flush()
