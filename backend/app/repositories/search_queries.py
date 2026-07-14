from collections.abc import Collection
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SearchStatus
from app.db.models import SearchQuery
from app.domain.jobs.types import SortDirection
from app.domain.sourcing.types import (
    GeneratedQuery,
    SearchQueryFilters,
    SearchQuerySort,
    SearchQuerySortField,
)
from app.repositories.base import BaseRepository


class SearchQueryRepository(BaseRepository[SearchQuery]):
    def __init__(self) -> None:
        super().__init__(SearchQuery)

    async def create_many(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        queries: tuple[GeneratedQuery, ...],
    ) -> list[SearchQuery]:
        records = [
            SearchQuery(
                job_id=job_id,
                source=query.source,
                language=query.language,
                query_text=query.query_text,
                normalized_query_key=query.normalized_query_key,
                query_type=query.query_type.value,
                precision_level=query.precision_level,
                expected_intent=query.expected_intent,
                included_titles=list(query.included_titles),
                included_skills=list(query.included_skills),
                included_locations=list(query.included_locations),
                status=SearchStatus.READY,
            )
            for query in queries
        ]
        session.add_all(records)
        await session.flush()
        return records

    async def get_by_id_for_job(
        self, session: AsyncSession, query_id: UUID, job_id: UUID
    ) -> SearchQuery | None:
        statement = select(SearchQuery).where(
            SearchQuery.id == query_id, SearchQuery.job_id == job_id
        )
        return cast(SearchQuery | None, await session.scalar(statement))

    async def list_by_job(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        offset: int,
        limit: int,
        filters: SearchQueryFilters,
        sort: SearchQuerySort,
    ) -> list[SearchQuery]:
        order_column = self._sort_column(sort.field)
        order = order_column.asc() if sort.direction is SortDirection.ASC else order_column.desc()
        statement = (
            select(SearchQuery)
            .where(SearchQuery.job_id == job_id, *self._filter_conditions(filters))
            .order_by(order, SearchQuery.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list((await session.scalars(statement)).all())

    async def count_by_job(
        self, session: AsyncSession, *, job_id: UUID, filters: SearchQueryFilters
    ) -> int:
        statement = select(func.count(SearchQuery.id)).where(
            SearchQuery.job_id == job_id, *self._filter_conditions(filters)
        )
        return int((await session.scalar(statement)) or 0)

    async def find_existing_keys(
        self, session: AsyncSession, *, job_id: UUID, keys: Collection[str]
    ) -> set[str]:
        if not keys:
            return set()
        statement = select(SearchQuery.normalized_query_key).where(
            SearchQuery.job_id == job_id,
            SearchQuery.normalized_query_key.in_(keys),
        )
        return set((await session.scalars(statement)).all())

    async def list_by_keys(
        self, session: AsyncSession, *, job_id: UUID, keys: Collection[str]
    ) -> list[SearchQuery]:
        if not keys:
            return []
        statement = select(SearchQuery).where(
            SearchQuery.job_id == job_id,
            SearchQuery.normalized_query_key.in_(keys),
        )
        return list((await session.scalars(statement)).all())

    async def delete(self, session: AsyncSession, *, query: SearchQuery) -> None:
        await session.delete(query)
        await session.flush()

    async def update_status(
        self,
        session: AsyncSession,
        *,
        query: SearchQuery,
        status: SearchStatus,
        executed_at: datetime | None = None,
    ) -> SearchQuery:
        query.status = status
        query.executed_at = executed_at
        await session.flush()
        return query

    async def update_result_count(
        self, session: AsyncSession, *, query: SearchQuery, result_count: int
    ) -> SearchQuery:
        query.result_count = result_count
        await session.flush()
        return query

    async def exists(self, session: AsyncSession, query_id: UUID) -> bool:
        statement = select(SearchQuery.id).where(SearchQuery.id == query_id).limit(1)
        return (await session.scalar(statement)) is not None

    @staticmethod
    def _filter_conditions(filters: SearchQueryFilters) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if filters.source is not None:
            conditions.append(SearchQuery.source == filters.source)
        if filters.language is not None:
            conditions.append(SearchQuery.language == filters.language)
        if filters.status is not None:
            conditions.append(SearchQuery.status == filters.status)
        if filters.query_type is not None:
            conditions.append(SearchQuery.query_type == filters.query_type.value)
        if filters.precision_level is not None:
            conditions.append(SearchQuery.precision_level == filters.precision_level)
        return conditions

    @staticmethod
    def _sort_column(field: SearchQuerySortField) -> ColumnElement[object]:
        fields = {
            SearchQuerySortField.CREATED_AT: SearchQuery.created_at,
            SearchQuerySortField.PRECISION_LEVEL: SearchQuery.precision_level,
            SearchQuerySortField.LANGUAGE: SearchQuery.language,
            SearchQuerySortField.RESULT_COUNT: SearchQuery.result_count,
        }
        return cast(ColumnElement[object], fields[field])
