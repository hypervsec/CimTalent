from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import JobStatus, SearchLanguage
from app.db.models import SearchQuery
from app.domain.jobs import JobNotFoundError
from app.domain.sourcing import (
    DuplicateSearchQueryError,
    JobNotParsedError,
    JobQueryGenerationStateError,
    QueryGenerationError,
    SearchQueryNotFoundError,
    SearchQueryPersistenceError,
)
from app.domain.sourcing.types import (
    QueryGenerationInput,
    QueryRequirementInput,
    SearchQueryFilters,
    SearchQuerySort,
)
from app.repositories.job_requirements import JobRequirementRepository
from app.repositories.jobs import JobRepository
from app.repositories.search_queries import SearchQueryRepository
from app.sourcing.query_generator import GoogleXRayQueryGenerator


@dataclass(frozen=True, slots=True)
class QueryGenerationOutcome:
    job_id: UUID
    generated_count: int
    created_count: int
    existing_count: int
    skipped_count: int
    queries: tuple[SearchQuery, ...]


@dataclass(frozen=True, slots=True)
class PagedSearchQueries:
    items: tuple[SearchQuery, ...]
    page: int
    page_size: int
    total_items: int


class QueryGenerationService:
    def __init__(
        self,
        job_repository: JobRepository,
        requirement_repository: JobRequirementRepository,
        query_repository: SearchQueryRepository,
        generator: GoogleXRayQueryGenerator,
    ) -> None:
        self.job_repository = job_repository
        self.requirement_repository = requirement_repository
        self.query_repository = query_repository
        self.generator = generator

    async def generate(
        self,
        session: AsyncSession,
        job_id: UUID,
        *,
        max_queries: int,
        languages: tuple[SearchLanguage, ...],
        target_domain: str,
    ) -> QueryGenerationOutcome:
        job = await self.job_repository.get_by_id(session, job_id)
        if job is None:
            raise JobNotFoundError(details={"job_id": str(job_id)})
        if job.status is JobStatus.DRAFT:
            raise JobNotParsedError(details={"job_id": str(job_id)})
        if job.status is JobStatus.ARCHIVED:
            raise JobQueryGenerationStateError(details={"job_id": str(job_id)})
        requirements = await self.requirement_repository.list_by_job_id(session, job_id)
        generated = self.generator.generate(
            QueryGenerationInput(
                job_id=job.id,
                job_title=job.title,
                city=job.city,
                country=job.country,
                required_skills=self._strings(job.required_skills),
                preferred_skills=self._strings(job.preferred_skills),
                keywords_tr=self._strings(job.keywords_tr),
                keywords_en=self._strings(job.keywords_en),
                requirements=tuple(
                    QueryRequirementInput(
                        type=item.type,
                        normalized_value=item.normalized_value,
                        raw_value=item.raw_value,
                        importance=item.importance,
                        weight=item.weight,
                        confidence=item.confidence,
                    )
                    for item in requirements
                ),
                max_queries=max_queries,
                languages=languages,
                target_domain=target_domain,
            )
        )
        if not generated:
            raise QueryGenerationError("No valid query could be generated.")
        keys = {item.normalized_query_key for item in generated}
        existing_keys = await self.query_repository.find_existing_keys(
            session, job_id=job_id, keys=keys
        )
        new_queries = tuple(
            item for item in generated if item.normalized_query_key not in existing_keys
        )
        try:
            await self.query_repository.create_many(session, job_id=job_id, queries=new_queries)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise DuplicateSearchQueryError(details={"job_id": str(job_id)}) from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            raise SearchQueryPersistenceError() from exc

        all_records = await self.query_repository.list_by_keys(session, job_id=job_id, keys=keys)
        by_key = {record.normalized_query_key: record for record in all_records}
        ordered = tuple(
            by_key[item.normalized_query_key]
            for item in generated
            if item.normalized_query_key in by_key
        )
        return QueryGenerationOutcome(
            job_id=job_id,
            generated_count=len(generated),
            created_count=len(new_queries),
            existing_count=len(existing_keys),
            skipped_count=len(generated) - len(new_queries),
            queries=ordered,
        )

    async def list_for_job(
        self,
        session: AsyncSession,
        job_id: UUID,
        *,
        page: int,
        page_size: int,
        filters: SearchQueryFilters,
        sort: SearchQuerySort,
    ) -> PagedSearchQueries:
        if not await self.job_repository.exists(session, job_id):
            raise JobNotFoundError(details={"job_id": str(job_id)})
        items = await self.query_repository.list_by_job(
            session,
            job_id=job_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            filters=filters,
            sort=sort,
        )
        total = await self.query_repository.count_by_job(session, job_id=job_id, filters=filters)
        return PagedSearchQueries(tuple(items), page, page_size, total)

    async def get(self, session: AsyncSession, query_id: UUID) -> SearchQuery:
        query = await self.query_repository.get_by_id(session, query_id)
        if query is None:
            raise SearchQueryNotFoundError(details={"query_id": str(query_id)})
        return query

    async def delete(self, session: AsyncSession, query_id: UUID) -> None:
        query = await self.get(session, query_id)
        try:
            await self.query_repository.delete(session, query=query)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            raise SearchQueryPersistenceError() from exc

    @staticmethod
    def _strings(values: list[object]) -> tuple[str, ...]:
        return tuple(value for value in values if isinstance(value, str))
