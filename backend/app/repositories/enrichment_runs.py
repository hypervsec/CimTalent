from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CandidateEnrichmentRun
from app.domain.enrichment.enums import (
    CandidateEnrichmentStatus,
    EnrichmentMode,
    EnrichmentProvider,
)


class EnrichmentRunRepository:
    async def create(
        self, session: AsyncSession, *, data: Mapping[str, object]
    ) -> CandidateEnrichmentRun:
        run = CandidateEnrichmentRun(**dict(data))
        session.add(run)
        await session.flush()
        return run

    async def get_by_id(self, session: AsyncSession, run_id: UUID) -> CandidateEnrichmentRun | None:
        return await session.get(CandidateEnrichmentRun, run_id)

    async def list_by_candidate(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        *,
        offset: int,
        limit: int,
        provider: EnrichmentProvider | None = None,
        mode: EnrichmentMode | None = None,
        status: CandidateEnrichmentStatus | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        sort_by: str = "created_at",
        descending: bool = True,
    ) -> list[CandidateEnrichmentRun]:
        statement = select(CandidateEnrichmentRun).where(
            CandidateEnrichmentRun.candidate_id == candidate_id
        )
        if provider is not None:
            statement = statement.where(CandidateEnrichmentRun.provider == provider)
        if mode is not None:
            statement = statement.where(CandidateEnrichmentRun.mode == mode)
        if status is not None:
            statement = statement.where(CandidateEnrichmentRun.status == status)
        if created_from is not None:
            statement = statement.where(CandidateEnrichmentRun.created_at >= created_from)
        if created_to is not None:
            statement = statement.where(CandidateEnrichmentRun.created_at <= created_to)
        columns = {
            "created_at": CandidateEnrichmentRun.created_at,
            "completed_at": CandidateEnrichmentRun.completed_at,
            "status": CandidateEnrichmentRun.status,
        }
        order = columns[sort_by].desc() if descending else columns[sort_by].asc()
        return list(
            (
                await session.scalars(
                    statement.order_by(order, CandidateEnrichmentRun.id).offset(offset).limit(limit)
                )
            ).all()
        )

    async def count_by_candidate(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        *,
        provider: EnrichmentProvider | None = None,
        mode: EnrichmentMode | None = None,
        status: CandidateEnrichmentStatus | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> int:
        statement = select(func.count(CandidateEnrichmentRun.id)).where(
            CandidateEnrichmentRun.candidate_id == candidate_id
        )
        for value, column in (
            (provider, CandidateEnrichmentRun.provider),
            (mode, CandidateEnrichmentRun.mode),
            (status, CandidateEnrichmentRun.status),
        ):
            if value is not None:
                statement = statement.where(column == value)
        if created_from is not None:
            statement = statement.where(CandidateEnrichmentRun.created_at >= created_from)
        if created_to is not None:
            statement = statement.where(CandidateEnrichmentRun.created_at <= created_to)
        return int((await session.scalar(statement)) or 0)

    async def update_status(
        self,
        session: AsyncSession,
        run: CandidateEnrichmentRun,
        status: CandidateEnrichmentStatus,
        *,
        changes: Mapping[str, object] | None = None,
    ) -> CandidateEnrichmentRun:
        run.status = status
        for name, value in (changes or {}).items():
            setattr(run, name, value)
        await session.flush()
        return run
