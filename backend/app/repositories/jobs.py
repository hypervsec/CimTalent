from __future__ import annotations

import builtins
from collections.abc import Mapping
from typing import cast
from uuid import UUID

from sqlalchemy import ColumnElement, Row, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import JobSource
from app.db.models import (
    CandidateMatch,
    JobPosting,
    JobRequirement,
    SearchQuery,
    ShortlistEntry,
)
from app.domain.jobs.types import (
    JobListFilters,
    JobSort,
    JobSortField,
    JobWithCounts,
    SortDirection,
)
from app.repositories.base import BaseRepository

JobCountRow = tuple[JobPosting, int, int, int, int]


class JobRepository(BaseRepository[JobPosting]):
    def __init__(self) -> None:
        super().__init__(JobPosting)

    async def create(
        self,
        session: AsyncSession,
        *,
        data: Mapping[str, object],
    ) -> JobPosting:
        job = JobPosting(**dict(data))
        session.add(job)
        await session.flush()
        return job

    async def get_by_id_with_counts(
        self, session: AsyncSession, job_id: UUID
    ) -> JobWithCounts | None:
        result = await session.execute(self._select_with_counts().where(JobPosting.id == job_id))
        row = result.one_or_none()
        return None if row is None else self._row_to_counts(row)

    async def list(
        self,
        session: AsyncSession,
        *,
        offset: int,
        limit: int,
        filters: JobListFilters,
        sort: JobSort,
    ) -> list[JobWithCounts]:
        order_column = self._sort_column(sort.field)
        order_expression = (
            order_column.asc() if sort.direction is SortDirection.ASC else order_column.desc()
        )
        statement = (
            self._select_with_counts()
            .where(*self._filter_expressions(filters))
            .order_by(order_expression, JobPosting.id.asc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await session.execute(statement)).all()
        return [self._row_to_counts(row) for row in rows]

    async def count(self, session: AsyncSession, *, filters: JobListFilters) -> int:
        statement = select(func.count(JobPosting.id)).where(*self._filter_expressions(filters))
        return int((await session.scalar(statement)) or 0)

    async def update(
        self,
        session: AsyncSession,
        *,
        job: JobPosting,
        changes: Mapping[str, object],
    ) -> JobPosting:
        for field_name, value in changes.items():
            setattr(job, field_name, value)
        await session.flush()
        return job

    async def delete(self, session: AsyncSession, *, job: JobPosting) -> None:
        await session.delete(job)
        await session.flush()

    async def exists(self, session: AsyncSession, job_id: UUID) -> bool:
        statement = select(JobPosting.id).where(JobPosting.id == job_id).limit(1)
        return (await session.scalar(statement)) is not None

    async def list_requirements(
        self, session: AsyncSession, job_id: UUID
    ) -> builtins.list[JobRequirement]:
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
        return builtins.list((await session.scalars(statement)).all())

    async def find_duplicate(
        self,
        session: AsyncSession,
        *,
        company_name: str,
        title: str,
        source: JobSource,
        source_url: str | None,
        description_raw: str,
        exclude_id: UUID | None = None,
    ) -> JobPosting | None:
        conditions: list[ColumnElement[bool]] = [
            func.lower(func.trim(JobPosting.company_name)) == company_name,
            func.lower(func.trim(JobPosting.title)) == title,
            JobPosting.source == source,
        ]
        if source_url is not None:
            conditions.append(JobPosting.source_url == source_url)
        else:
            conditions.extend(
                [
                    JobPosting.source_url.is_(None),
                    func.lower(func.trim(JobPosting.description_raw)) == description_raw,
                ]
            )
        if exclude_id is not None:
            conditions.append(JobPosting.id != exclude_id)
        statement = select(JobPosting).where(*conditions).limit(1)
        return cast(JobPosting | None, await session.scalar(statement))

    @staticmethod
    def _select_with_counts() -> Select[JobCountRow]:
        requirement_count = (
            select(func.count(JobRequirement.id))
            .where(JobRequirement.job_id == JobPosting.id)
            .correlate(JobPosting)
            .scalar_subquery()
        )
        search_query_count = (
            select(func.count(SearchQuery.id))
            .where(SearchQuery.job_id == JobPosting.id)
            .correlate(JobPosting)
            .scalar_subquery()
        )
        candidate_match_count = (
            select(func.count(CandidateMatch.id))
            .where(CandidateMatch.job_id == JobPosting.id)
            .correlate(JobPosting)
            .scalar_subquery()
        )
        shortlist_count = (
            select(func.count(ShortlistEntry.id))
            .where(ShortlistEntry.job_id == JobPosting.id)
            .correlate(JobPosting)
            .scalar_subquery()
        )
        return select(
            JobPosting,
            requirement_count,
            search_query_count,
            candidate_match_count,
            shortlist_count,
        )

    @staticmethod
    def _row_to_counts(row: Row[JobCountRow]) -> JobWithCounts:
        job, requirements, queries, matches, shortlist = row._tuple()
        return JobWithCounts(
            job=job,
            requirement_count=int(requirements),
            search_query_count=int(queries),
            candidate_match_count=int(matches),
            shortlist_count=int(shortlist),
        )

    @staticmethod
    def _filter_expressions(
        filters: JobListFilters,
    ) -> builtins.list[ColumnElement[bool]]:
        expressions: builtins.list[ColumnElement[bool]] = []
        if filters.status is not None:
            expressions.append(JobPosting.status == filters.status)
        if filters.source is not None:
            expressions.append(JobPosting.source == filters.source)
        if city := JobRepository._clean_filter(filters.city):
            expressions.append(func.lower(JobPosting.city) == city.casefold())
        if company_name := JobRepository._clean_filter(filters.company_name):
            expressions.append(
                func.lower(JobPosting.company_name).contains(
                    company_name.casefold(), autoescape=True
                )
            )
        if title := JobRepository._clean_filter(filters.title):
            expressions.append(
                func.lower(JobPosting.title).contains(title.casefold(), autoescape=True)
            )
        if search_term := JobRepository._clean_filter(filters.search):
            normalized = search_term.casefold()
            expressions.append(
                or_(
                    func.lower(JobPosting.title).contains(normalized, autoescape=True),
                    func.lower(JobPosting.company_name).contains(normalized, autoescape=True),
                    func.lower(JobPosting.description_raw).contains(normalized, autoescape=True),
                    func.lower(JobPosting.city).contains(normalized, autoescape=True),
                )
            )
        if filters.created_from is not None:
            expressions.append(JobPosting.created_at >= filters.created_from)
        if filters.created_to is not None:
            expressions.append(JobPosting.created_at <= filters.created_to)
        return expressions

    @staticmethod
    def _sort_column(field: JobSortField) -> ColumnElement[object]:
        fields = {
            JobSortField.CREATED_AT: JobPosting.created_at,
            JobSortField.UPDATED_AT: JobPosting.updated_at,
            JobSortField.TITLE: JobPosting.title,
            JobSortField.COMPANY_NAME: JobPosting.company_name,
            JobSortField.STATUS: JobPosting.status,
        }
        return cast(ColumnElement[object], fields[field])

    @staticmethod
    def _clean_filter(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
