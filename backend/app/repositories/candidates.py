from __future__ import annotations

import builtins
from collections.abc import Collection, Mapping
from typing import Any, cast
from uuid import UUID

from sqlalchemy import ColumnElement, Row, Select, delete, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Candidate,
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateLanguage,
    CandidateMatch,
    CandidateMergeAudit,
    CandidateSkill,
    SearchQuery,
    SearchResult,
    ShortlistEntry,
)
from app.domain.candidates.types import (
    CandidateListFilters,
    CandidateSort,
    CandidateSortField,
    CandidateWithCounts,
)
from app.domain.jobs.types import SortDirection
from app.repositories.base import BaseRepository

CandidateCountRow = tuple[Candidate, int, int, int, int, int, int, int, int]


class CandidateRepository(BaseRepository[Candidate]):
    def __init__(self) -> None:
        super().__init__(Candidate)

    async def create(self, session: AsyncSession, *, data: Mapping[str, object]) -> Candidate:
        candidate = Candidate(**dict(data))
        session.add(candidate)
        await session.flush()
        return candidate

    async def get_by_id_with_counts(
        self, session: AsyncSession, candidate_id: UUID
    ) -> CandidateWithCounts | None:
        row = (
            await session.execute(self._select_with_counts().where(Candidate.id == candidate_id))
        ).one_or_none()
        return None if row is None else self._row_to_counts(row)

    async def get_by_normalized_profile_url(
        self, session: AsyncSession, normalized_url: str
    ) -> Candidate | None:
        return cast(
            Candidate | None,
            await session.scalar(
                select(Candidate).where(Candidate.normalized_profile_url == normalized_url).limit(1)
            ),
        )

    async def get_by_linkedin_slug(
        self, session: AsyncSession, profile_slug: str
    ) -> Candidate | None:
        return cast(
            Candidate | None,
            await session.scalar(
                select(Candidate)
                .where(func.lower(Candidate.profile_slug) == profile_slug.casefold())
                .order_by(Candidate.created_at.asc(), Candidate.id.asc())
                .limit(1)
            ),
        )

    async def list(
        self,
        session: AsyncSession,
        *,
        offset: int,
        limit: int,
        filters: CandidateListFilters,
        sort: CandidateSort,
    ) -> list[CandidateWithCounts]:
        order_column = self._sort_column(sort.field)
        order = order_column.asc() if sort.direction is SortDirection.ASC else order_column.desc()
        rows = (
            await session.execute(
                self._select_with_counts()
                .where(*self._filter_expressions(filters))
                .order_by(order, Candidate.id.asc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [self._row_to_counts(row) for row in rows]

    async def count(self, session: AsyncSession, *, filters: CandidateListFilters) -> int:
        statement = select(func.count(Candidate.id)).where(*self._filter_expressions(filters))
        return int((await session.scalar(statement)) or 0)

    async def update(
        self,
        session: AsyncSession,
        *,
        candidate: Candidate,
        changes: Mapping[str, object],
    ) -> Candidate:
        for field_name, value in changes.items():
            setattr(candidate, field_name, value)
        await session.flush()
        return candidate

    async def delete(self, session: AsyncSession, *, candidate: Candidate) -> None:
        await session.delete(candidate)
        await session.flush()

    async def exists(self, session: AsyncSession, candidate_id: UUID) -> bool:
        return (
            await session.scalar(select(Candidate.id).where(Candidate.id == candidate_id).limit(1))
        ) is not None

    async def list_search_results(
        self, session: AsyncSession, candidate_id: UUID
    ) -> builtins.list[SearchResult]:
        statement = (
            select(SearchResult)
            .where(SearchResult.candidate_id == candidate_id)
            .options(selectinload(SearchResult.search_query).selectinload(SearchQuery.job))
            .order_by(SearchResult.discovered_at.asc(), SearchResult.id.asc())
        )
        return builtins.list((await session.scalars(statement)).all())

    async def attach_search_result(
        self, session: AsyncSession, *, result: SearchResult, candidate_id: UUID
    ) -> None:
        result.candidate_id = candidate_id
        await session.flush()

    async def attach_search_results(
        self, session: AsyncSession, *, result_ids: Collection[UUID], candidate_id: UUID
    ) -> int:
        if not result_ids:
            return 0
        result = cast(
            CursorResult[Any],
            await session.execute(
                update(SearchResult)
                .where(SearchResult.id.in_(result_ids))
                .values(candidate_id=candidate_id)
            ),
        )
        await session.flush()
        return int(result.rowcount or 0)

    async def detach_search_result(self, session: AsyncSession, result_id: UUID) -> None:
        await session.execute(
            update(SearchResult).where(SearchResult.id == result_id).values(candidate_id=None)
        )
        await session.flush()

    async def move_search_results(
        self, session: AsyncSession, *, source_ids: Collection[UUID], target_id: UUID
    ) -> int:
        if not source_ids:
            return 0
        result = cast(
            CursorResult[Any],
            await session.execute(
                update(SearchResult)
                .where(SearchResult.candidate_id.in_(source_ids))
                .values(candidate_id=target_id)
            ),
        )
        await session.flush()
        return int(result.rowcount or 0)

    async def move_children(
        self,
        session: AsyncSession,
        *,
        model: type[CandidateExperience]
        | type[CandidateEducation]
        | type[CandidateSkill]
        | type[CandidateCertification]
        | type[CandidateLanguage],
        source_ids: Collection[UUID],
        target_id: UUID,
    ) -> int:
        if not source_ids:
            return 0
        result = cast(
            CursorResult[Any],
            await session.execute(
                update(model)
                .where(model.candidate_id.in_(source_ids))
                .values(candidate_id=target_id)
            ),
        )
        await session.flush()
        return int(result.rowcount or 0)

    async def lock_by_id(self, session: AsyncSession, candidate_id: UUID) -> Candidate | None:
        return cast(
            Candidate | None,
            await session.scalar(
                select(Candidate).where(Candidate.id == candidate_id).with_for_update()
            ),
        )

    async def list_by_ids(
        self, session: AsyncSession, candidate_ids: Collection[UUID]
    ) -> builtins.list[Candidate]:
        if not candidate_ids:
            return []
        return builtins.list(
            (await session.scalars(select(Candidate).where(Candidate.id.in_(candidate_ids)))).all()
        )

    async def find_duplicate_candidates(
        self, session: AsyncSession, candidate: Candidate, *, limit: int = 100
    ) -> builtins.list[Candidate]:
        signals: builtins.list[ColumnElement[bool]] = []
        if candidate.normalized_profile_url:
            signals.append(Candidate.normalized_profile_url == candidate.normalized_profile_url)
        if candidate.profile_slug:
            signals.append(func.lower(Candidate.profile_slug) == candidate.profile_slug.casefold())
        if candidate.full_name:
            signals.append(func.lower(Candidate.full_name) == candidate.full_name.casefold())
        if not signals:
            return []
        statement = (
            select(Candidate)
            .where(Candidate.id != candidate.id, or_(*signals))
            .order_by(Candidate.created_at.asc(), Candidate.id.asc())
            .limit(limit)
        )
        return builtins.list((await session.scalars(statement)).all())

    async def create_merge_audit(
        self, session: AsyncSession, *, data: Mapping[str, object]
    ) -> CandidateMergeAudit:
        audit = CandidateMergeAudit(**dict(data))
        session.add(audit)
        await session.flush()
        return audit

    async def list_skills_by_candidates(
        self, session: AsyncSession, candidate_ids: Collection[UUID]
    ) -> builtins.list[CandidateSkill]:
        if not candidate_ids:
            return []
        return builtins.list(
            (
                await session.scalars(
                    select(CandidateSkill)
                    .where(CandidateSkill.candidate_id.in_(candidate_ids))
                    .order_by(CandidateSkill.created_at.asc(), CandidateSkill.id.asc())
                )
            ).all()
        )

    async def list_languages_by_candidates(
        self, session: AsyncSession, candidate_ids: Collection[UUID]
    ) -> builtins.list[CandidateLanguage]:
        if not candidate_ids:
            return []
        return builtins.list(
            (
                await session.scalars(
                    select(CandidateLanguage)
                    .where(CandidateLanguage.candidate_id.in_(candidate_ids))
                    .order_by(CandidateLanguage.created_at.asc(), CandidateLanguage.id.asc())
                )
            ).all()
        )

    async def list_matches_by_candidates(
        self, session: AsyncSession, candidate_ids: Collection[UUID]
    ) -> builtins.list[CandidateMatch]:
        if not candidate_ids:
            return []
        return builtins.list(
            (
                await session.scalars(
                    select(CandidateMatch)
                    .where(CandidateMatch.candidate_id.in_(candidate_ids))
                    .order_by(CandidateMatch.created_at.asc(), CandidateMatch.id.asc())
                )
            ).all()
        )

    async def list_shortlist_by_candidates(
        self, session: AsyncSession, candidate_ids: Collection[UUID]
    ) -> builtins.list[ShortlistEntry]:
        if not candidate_ids:
            return []
        return builtins.list(
            (
                await session.scalars(
                    select(ShortlistEntry)
                    .where(ShortlistEntry.candidate_id.in_(candidate_ids))
                    .order_by(ShortlistEntry.created_at.asc(), ShortlistEntry.id.asc())
                )
            ).all()
        )

    async def delete_merge_records(
        self,
        session: AsyncSession,
        records: Collection[CandidateSkill | CandidateLanguage | CandidateMatch | ShortlistEntry],
    ) -> None:
        for record in records:
            await session.delete(record)
        await session.flush()

    async def delete_candidates(
        self, session: AsyncSession, candidate_ids: Collection[UUID]
    ) -> int:
        if not candidate_ids:
            return 0
        result = cast(
            CursorResult[Any],
            await session.execute(delete(Candidate).where(Candidate.id.in_(candidate_ids))),
        )
        await session.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def _select_with_counts() -> Select[CandidateCountRow]:
        models = (
            CandidateExperience,
            CandidateEducation,
            CandidateSkill,
            CandidateCertification,
            CandidateLanguage,
            SearchResult,
            CandidateMatch,
            ShortlistEntry,
        )
        counts = tuple(
            select(func.count(model.id))
            .where(model.candidate_id == Candidate.id)
            .correlate(Candidate)
            .scalar_subquery()
            for model in models
        )
        return select(Candidate, *counts)

    @staticmethod
    def _row_to_counts(row: Row[CandidateCountRow]) -> CandidateWithCounts:
        candidate, *counts = row._tuple()
        return CandidateWithCounts(candidate, *(int(value) for value in counts))

    @staticmethod
    def _filter_expressions(filters: CandidateListFilters) -> builtins.list[ColumnElement[bool]]:
        expressions: builtins.list[ColumnElement[bool]] = []
        exact = (
            (filters.source, Candidate.source),
            (filters.profile_status, Candidate.profile_status),
            (filters.city, Candidate.city),
            (filters.country, Candidate.country),
            (filters.current_title, Candidate.current_title),
            (filters.current_company, Candidate.current_company),
        )
        for value, column in exact:
            if value is not None:
                expressions.append(func.lower(column) == str(value).casefold())
        if filters.min_data_quality is not None:
            expressions.append(Candidate.data_quality_score >= filters.min_data_quality)
        if filters.max_data_quality is not None:
            expressions.append(Candidate.data_quality_score <= filters.max_data_quality)
        if filters.min_experience_months is not None:
            expressions.append(Candidate.total_experience_months >= filters.min_experience_months)
        if filters.max_experience_months is not None:
            expressions.append(Candidate.total_experience_months <= filters.max_experience_months)
        if filters.has_profile_url is not None:
            profile_expression = Candidate.normalized_profile_url.is_not(None)
            expressions.append(
                profile_expression if filters.has_profile_url else ~profile_expression
            )
        if filters.has_search_results is not None:
            search_result_expression = (
                select(SearchResult.id).where(SearchResult.candidate_id == Candidate.id).exists()
            )
            expressions.append(
                search_result_expression
                if filters.has_search_results
                else ~search_result_expression
            )
        if filters.skill:
            expressions.append(
                select(CandidateSkill.id)
                .where(
                    CandidateSkill.candidate_id == Candidate.id,
                    func.lower(CandidateSkill.normalized_name) == filters.skill.casefold(),
                )
                .exists()
            )
        if filters.education_field:
            expressions.append(
                select(CandidateEducation.id)
                .where(
                    CandidateEducation.candidate_id == Candidate.id,
                    func.lower(CandidateEducation.field_of_study_normalized)
                    == filters.education_field.casefold(),
                )
                .exists()
            )
        if filters.search and filters.search.strip():
            term = filters.search.strip().casefold()
            columns = (
                Candidate.full_name,
                Candidate.headline,
                Candidate.current_title,
                Candidate.current_company,
                Candidate.city,
                Candidate.country,
                Candidate.discovery_title,
                Candidate.discovery_snippet,
            )
            expressions.append(
                or_(*(func.lower(column).contains(term, autoescape=True) for column in columns))
            )
        if filters.created_from is not None:
            expressions.append(Candidate.created_at >= filters.created_from)
        if filters.created_to is not None:
            expressions.append(Candidate.created_at <= filters.created_to)
        return expressions

    @staticmethod
    def _sort_column(field: CandidateSortField) -> ColumnElement[object]:
        fields = {
            CandidateSortField.CREATED_AT: Candidate.created_at,
            CandidateSortField.UPDATED_AT: Candidate.updated_at,
            CandidateSortField.FULL_NAME: Candidate.full_name,
            CandidateSortField.DATA_QUALITY_SCORE: Candidate.data_quality_score,
            CandidateSortField.TOTAL_EXPERIENCE_MONTHS: Candidate.total_experience_months,
            CandidateSortField.CURRENT_TITLE: Candidate.current_title,
            CandidateSortField.CURRENT_COMPANY: Candidate.current_company,
        }
        return cast(ColumnElement[object], fields[field])
