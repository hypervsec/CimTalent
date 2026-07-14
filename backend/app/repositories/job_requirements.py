from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobRequirement
from app.domain.jobs.parser_types import ParsedRequirement
from app.repositories.base import BaseRepository


class JobRequirementRepository(BaseRepository[JobRequirement]):
    def __init__(self) -> None:
        super().__init__(JobRequirement)

    async def list_by_job_id(self, session: AsyncSession, job_id: UUID) -> list[JobRequirement]:
        statement = (
            select(JobRequirement)
            .where(JobRequirement.job_id == job_id)
            .order_by(
                JobRequirement.type.asc(),
                JobRequirement.normalized_value.asc(),
                JobRequirement.importance.asc(),
                JobRequirement.id.asc(),
            )
        )
        return list((await session.scalars(statement)).all())

    async def delete_by_job_id(self, session: AsyncSession, job_id: UUID) -> None:
        await session.execute(delete(JobRequirement).where(JobRequirement.job_id == job_id))

    async def bulk_create(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        requirements: tuple[ParsedRequirement, ...],
    ) -> list[JobRequirement]:
        records = [
            JobRequirement(
                job_id=job_id,
                type=requirement.type,
                raw_value=requirement.raw_value,
                normalized_value=requirement.normalized_value,
                importance=requirement.importance,
                weight=requirement.weight,
                confidence=requirement.confidence,
                source=requirement.source,
            )
            for requirement in requirements
        ]
        session.add_all(records)
        await session.flush()
        return records

    async def replace_for_job(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        requirements: tuple[ParsedRequirement, ...],
    ) -> list[JobRequirement]:
        await self.delete_by_job_id(session, job_id)
        return await self.bulk_create(session, job_id=job_id, requirements=requirements)

    async def count_by_job_id(self, session: AsyncSession, job_id: UUID) -> int:
        statement = select(func.count(JobRequirement.id)).where(JobRequirement.job_id == job_id)
        return int((await session.scalar(statement)) or 0)
