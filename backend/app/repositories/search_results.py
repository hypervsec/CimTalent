from collections.abc import Collection
from typing import cast
from uuid import UUID

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import SearchQuery, SearchResult
from app.domain.jobs.types import SortDirection
from app.domain.sourcing.types import (
    ParsedManualSearchResult,
    SearchResultFilters,
    SearchResultSort,
    SearchResultSortField,
)
from app.repositories.base import BaseRepository


class SearchResultRepository(BaseRepository[SearchResult]):
    def __init__(self) -> None:
        super().__init__(SearchResult)

    async def get_by_id_with_query(
        self, session: AsyncSession, result_id: UUID
    ) -> SearchResult | None:
        statement = (
            select(SearchResult)
            .where(SearchResult.id == result_id)
            .options(selectinload(SearchResult.search_query).selectinload(SearchQuery.job))
        )
        return cast(SearchResult | None, await session.scalar(statement))

    async def list_unassigned_by_job(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        limit: int,
        only_unassigned: bool = True,
    ) -> list[SearchResult]:
        conditions: list[ColumnElement[bool]] = [SearchQuery.job_id == job_id]
        if only_unassigned:
            conditions.append(SearchResult.candidate_id.is_(None))
        statement = (
            select(SearchResult)
            .join(SearchQuery, SearchQuery.id == SearchResult.search_query_id)
            .where(*conditions)
            .options(selectinload(SearchResult.search_query).selectinload(SearchQuery.job))
            .order_by(SearchResult.normalized_url.asc(), SearchResult.id.asc())
            .limit(limit)
        )
        return list((await session.scalars(statement)).all())

    async def assign_candidate(
        self, session: AsyncSession, *, result: SearchResult, candidate_id: UUID
    ) -> None:
        result.candidate_id = candidate_id
        await session.flush()

    async def count_unassigned_by_job(self, session: AsyncSession, job_id: UUID) -> int:
        statement = (
            select(func.count(SearchResult.id))
            .join(SearchQuery, SearchQuery.id == SearchResult.search_query_id)
            .where(SearchQuery.job_id == job_id, SearchResult.candidate_id.is_(None))
        )
        return int((await session.scalar(statement)) or 0)

    async def create_many(
        self,
        session: AsyncSession,
        *,
        query_id: UUID,
        results: tuple[ParsedManualSearchResult, ...],
        canonical: dict[str, SearchResult],
    ) -> list[SearchResult]:
        records = [
            SearchResult(
                search_query_id=query_id,
                source_url=result.source_url,
                normalized_url=result.normalized_url,
                source_domain=result.source_domain,
                title=result.title,
                snippet=result.snippet,
                displayed_name=result.displayed_name,
                displayed_headline=result.displayed_headline,
                displayed_location=result.displayed_location,
                result_rank=result.result_rank,
                is_duplicate=result.normalized_url in canonical,
                duplicate_of_id=(
                    canonical[result.normalized_url].id
                    if result.normalized_url in canonical
                    else None
                ),
            )
            for result in results
        ]
        session.add_all(records)
        await session.flush()
        return records

    async def list_by_query(
        self,
        session: AsyncSession,
        *,
        query_id: UUID,
        offset: int,
        limit: int,
        filters: SearchResultFilters,
        sort: SearchResultSort,
    ) -> list[SearchResult]:
        return await self._list(
            session,
            conditions=[SearchResult.search_query_id == query_id],
            offset=offset,
            limit=limit,
            filters=filters,
            sort=sort,
        )

    async def list_by_job(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        offset: int,
        limit: int,
        filters: SearchResultFilters,
        sort: SearchResultSort,
    ) -> list[SearchResult]:
        return await self._list(
            session,
            conditions=[SearchQuery.job_id == job_id],
            offset=offset,
            limit=limit,
            filters=filters,
            sort=sort,
        )

    async def count_by_query(
        self, session: AsyncSession, *, query_id: UUID, filters: SearchResultFilters
    ) -> int:
        return await self._count(session, [SearchResult.search_query_id == query_id], filters)

    async def count_by_job(
        self, session: AsyncSession, *, job_id: UUID, filters: SearchResultFilters
    ) -> int:
        return await self._count(session, [SearchQuery.job_id == job_id], filters)

    async def find_existing_urls_for_query(
        self, session: AsyncSession, *, query_id: UUID, urls: Collection[str]
    ) -> set[str]:
        if not urls:
            return set()
        statement = select(SearchResult.normalized_url).where(
            SearchResult.search_query_id == query_id,
            SearchResult.normalized_url.in_(urls),
        )
        return set((await session.scalars(statement)).all())

    async def find_canonical_by_normalized_urls(
        self,
        session: AsyncSession,
        *,
        urls: Collection[str],
        exclude_query_id: UUID,
    ) -> dict[str, SearchResult]:
        if not urls:
            return {}
        statement = (
            select(SearchResult)
            .where(
                SearchResult.normalized_url.in_(urls),
                SearchResult.search_query_id != exclude_query_id,
                SearchResult.duplicate_of_id.is_(None),
            )
            .order_by(SearchResult.discovered_at.asc(), SearchResult.id.asc())
        )
        records = (await session.scalars(statement)).all()
        output: dict[str, SearchResult] = {}
        for record in records:
            output.setdefault(record.normalized_url, record)
        return output

    async def delete_by_query(self, session: AsyncSession, query_id: UUID) -> None:
        await session.execute(delete(SearchResult).where(SearchResult.search_query_id == query_id))
        await session.flush()

    async def delete(self, session: AsyncSession, *, result: SearchResult) -> None:
        await session.delete(result)
        await session.flush()

    async def mark_duplicates(
        self,
        session: AsyncSession,
        *,
        records: Collection[SearchResult],
        canonical: SearchResult,
    ) -> None:
        for record in records:
            record.is_duplicate = True
            record.duplicate_of_id = canonical.id
        await session.flush()

    async def get_distinct_normalized_url_count(
        self, session: AsyncSession, *, job_id: UUID
    ) -> int:
        statement = (
            select(func.count(func.distinct(SearchResult.normalized_url)))
            .join(SearchQuery, SearchQuery.id == SearchResult.search_query_id)
            .where(SearchQuery.job_id == job_id)
        )
        return int((await session.scalar(statement)) or 0)

    async def _list(
        self,
        session: AsyncSession,
        *,
        conditions: list[ColumnElement[bool]],
        offset: int,
        limit: int,
        filters: SearchResultFilters,
        sort: SearchResultSort,
    ) -> list[SearchResult]:
        order_column = self._sort_column(sort.field)
        order = order_column.asc() if sort.direction is SortDirection.ASC else order_column.desc()
        statement = (
            select(SearchResult)
            .join(SearchQuery, SearchQuery.id == SearchResult.search_query_id)
            .where(*conditions, *self._filter_conditions(filters))
            .order_by(order, SearchResult.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list((await session.scalars(statement)).all())

    async def _count(
        self,
        session: AsyncSession,
        conditions: list[ColumnElement[bool]],
        filters: SearchResultFilters,
    ) -> int:
        statement = (
            select(func.count(SearchResult.id))
            .join(SearchQuery, SearchQuery.id == SearchResult.search_query_id)
            .where(*conditions, *self._filter_conditions(filters))
        )
        return int((await session.scalar(statement)) or 0)

    @staticmethod
    def _filter_conditions(filters: SearchResultFilters) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if filters.query_id is not None:
            conditions.append(SearchResult.search_query_id == filters.query_id)
        if filters.source_domain is not None:
            conditions.append(SearchResult.source_domain == filters.source_domain)
        if filters.is_duplicate is not None:
            conditions.append(SearchResult.is_duplicate == filters.is_duplicate)
        if filters.min_pre_score is not None:
            conditions.append(SearchResult.pre_score >= filters.min_pre_score)
        if filters.candidate_assigned is not None:
            candidate_condition = SearchResult.candidate_id.is_not(None)
            conditions.append(
                candidate_condition
                if filters.candidate_assigned
                else SearchResult.candidate_id.is_(None)
            )
        if filters.language is not None:
            conditions.append(SearchQuery.language == filters.language)
        if filters.query_type is not None:
            conditions.append(SearchQuery.query_type == filters.query_type.value)
        return conditions

    @staticmethod
    def _sort_column(field: SearchResultSortField) -> ColumnElement[object]:
        fields = {
            SearchResultSortField.DISCOVERED_AT: SearchResult.discovered_at,
            SearchResultSortField.RESULT_RANK: SearchResult.result_rank,
            SearchResultSortField.PRE_SCORE: SearchResult.pre_score,
            SearchResultSortField.TITLE: SearchResult.title,
        }
        return cast(ColumnElement[object], fields[field])
