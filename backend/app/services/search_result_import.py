from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SearchStatus
from app.db.models import SearchResult
from app.domain.jobs import JobNotFoundError
from app.domain.sourcing import (
    ManualImportValidationError,
    SearchQueryNotFoundError,
    SearchResultNotFoundError,
    SearchResultPersistenceError,
)
from app.domain.sourcing.types import (
    ImportMode,
    ManualImportFormat,
    ManualParseOutcome,
    ManualResultInputData,
    SearchResultFilters,
    SearchResultSort,
)
from app.repositories.jobs import JobRepository
from app.repositories.search_queries import SearchQueryRepository
from app.repositories.search_results import SearchResultRepository
from app.sourcing.manual_result_parser import ManualSearchResultParser


@dataclass(frozen=True, slots=True)
class SearchResultImportOutcome:
    query_id: UUID
    mode: ImportMode
    received_count: int
    valid_count: int
    inserted_count: int
    duplicate_count: int
    invalid_count: int
    total_query_result_count: int
    warnings: tuple[str, ...]
    results: tuple[SearchResult, ...]


@dataclass(frozen=True, slots=True)
class PagedSearchResults:
    items: tuple[SearchResult, ...]
    page: int
    page_size: int
    total_items: int


class SearchResultImportService:
    def __init__(
        self,
        job_repository: JobRepository,
        query_repository: SearchQueryRepository,
        result_repository: SearchResultRepository,
        parser: ManualSearchResultParser,
    ) -> None:
        self.job_repository = job_repository
        self.query_repository = query_repository
        self.result_repository = result_repository
        self.parser = parser

    async def import_results(
        self,
        session: AsyncSession,
        query_id: UUID,
        *,
        import_format: ManualImportFormat,
        mode: ImportMode,
        payload: str | tuple[str, ...] | tuple[ManualResultInputData, ...],
    ) -> SearchResultImportOutcome:
        query = await self.query_repository.get_by_id(session, query_id)
        if query is None:
            raise SearchQueryNotFoundError(details={"query_id": str(query_id)})
        parsed = self._parse(import_format, payload)
        urls = {item.normalized_url for item in parsed.results}
        existing_urls = (
            await self.result_repository.find_existing_urls_for_query(
                session, query_id=query_id, urls=urls
            )
            if mode is ImportMode.MERGE
            else set()
        )
        insertable = tuple(
            item for item in parsed.results if item.normalized_url not in existing_urls
        )
        try:
            if mode is ImportMode.REPLACE:
                await self.result_repository.delete_by_query(session, query_id)
            canonical = await self.result_repository.find_canonical_by_normalized_urls(
                session,
                urls={item.normalized_url for item in insertable},
                exclude_query_id=query_id,
            )
            records = await self.result_repository.create_many(
                session,
                query_id=query_id,
                results=insertable,
                canonical=canonical,
            )
            total = await self.result_repository.count_by_query(
                session, query_id=query_id, filters=SearchResultFilters()
            )
            await self.query_repository.update_result_count(
                session, query=query, result_count=total
            )
            await self.query_repository.update_status(
                session,
                query=query,
                status=SearchStatus.COMPLETED,
                executed_at=datetime.now(UTC),
            )
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            raise SearchResultPersistenceError(details={"query_id": str(query_id)}) from exc
        duplicate_count = parsed.duplicate_count + len(existing_urls) + len(canonical)
        return SearchResultImportOutcome(
            query_id=query_id,
            mode=mode,
            received_count=parsed.received_count,
            valid_count=parsed.received_count - parsed.invalid_count,
            inserted_count=len(records),
            duplicate_count=duplicate_count,
            invalid_count=parsed.invalid_count,
            total_query_result_count=total,
            warnings=parsed.warnings,
            results=tuple(records),
        )

    async def list_for_query(
        self,
        session: AsyncSession,
        query_id: UUID,
        *,
        page: int,
        page_size: int,
        filters: SearchResultFilters,
        sort: SearchResultSort,
    ) -> PagedSearchResults:
        if not await self.query_repository.exists(session, query_id):
            raise SearchQueryNotFoundError(details={"query_id": str(query_id)})
        items = await self.result_repository.list_by_query(
            session,
            query_id=query_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            filters=filters,
            sort=sort,
        )
        total = await self.result_repository.count_by_query(
            session, query_id=query_id, filters=filters
        )
        return PagedSearchResults(tuple(items), page, page_size, total)

    async def list_for_job(
        self,
        session: AsyncSession,
        job_id: UUID,
        *,
        page: int,
        page_size: int,
        filters: SearchResultFilters,
        sort: SearchResultSort,
    ) -> PagedSearchResults:
        if not await self.job_repository.exists(session, job_id):
            raise JobNotFoundError(details={"job_id": str(job_id)})
        items = await self.result_repository.list_by_job(
            session,
            job_id=job_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            filters=filters,
            sort=sort,
        )
        total = await self.result_repository.count_by_job(session, job_id=job_id, filters=filters)
        return PagedSearchResults(tuple(items), page, page_size, total)

    async def get(self, session: AsyncSession, result_id: UUID) -> SearchResult:
        result = await self.result_repository.get_by_id(session, result_id)
        if result is None:
            raise SearchResultNotFoundError(details={"result_id": str(result_id)})
        return result

    async def delete(self, session: AsyncSession, result_id: UUID) -> None:
        result = await self.get(session, result_id)
        try:
            await self.result_repository.delete(session, result=result)
            query = await self.query_repository.get_by_id(session, result.search_query_id)
            if query is not None:
                count = await self.result_repository.count_by_query(
                    session,
                    query_id=query.id,
                    filters=SearchResultFilters(),
                )
                await self.query_repository.update_result_count(
                    session, query=query, result_count=count
                )
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            raise SearchResultPersistenceError() from exc

    def _parse(
        self,
        import_format: ManualImportFormat,
        payload: str | tuple[str, ...] | tuple[ManualResultInputData, ...],
    ) -> ManualParseOutcome:
        if import_format is ManualImportFormat.HTML and isinstance(payload, str):
            return self.parser.parse_html(payload)
        if (
            import_format is ManualImportFormat.URLS
            and isinstance(payload, tuple)
            and all(isinstance(item, str) for item in payload)
        ):
            return self.parser.parse_urls(cast(tuple[str, ...], payload))
        if (
            import_format is ManualImportFormat.JSON
            and isinstance(payload, tuple)
            and all(isinstance(item, ManualResultInputData) for item in payload)
        ):
            return self.parser.parse_json(cast(tuple[ManualResultInputData, ...], payload))
        raise ManualImportValidationError()
