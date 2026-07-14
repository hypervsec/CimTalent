from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import (
    CandidateSkillSource,
    CandidateSource,
    JobSource,
    SearchLanguage,
    SearchSource,
)
from app.db.models import (
    CandidateEducation,
    CandidateExperience,
    CandidateSkill,
    SearchQuery,
    SearchResult,
)
from app.domain.candidates import (
    CandidateListFilters,
    CandidateSort,
    CandidateSortField,
)
from app.domain.jobs import SortDirection
from app.repositories.candidates import CandidateRepository
from app.repositories.jobs import JobRepository


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    database = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(database.sync_engine, "connect")
    def enable_foreign_keys(connection: Any, _: object) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    async with database.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield database
    await database.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(engine, expire_on_commit=False) as database_session:
        yield database_session


def data(name: str, **changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "source": CandidateSource.MANUAL,
        "full_name": name,
        "data_quality_score": 15.0,
    }
    values.update(changes)
    return values


async def test_create_get_update_delete(session: AsyncSession) -> None:
    repository = CandidateRepository()
    candidate = await repository.create(session, data=data("Demo Engineer"))
    assert await repository.get_by_id(session, candidate.id) is candidate
    assert await repository.exists(session, candidate.id)
    await repository.update(session, candidate=candidate, changes={"city": "Bursa"})
    assert candidate.city == "Bursa"
    await repository.delete(session, candidate=candidate)
    assert not await repository.exists(session, candidate.id)


async def test_exact_identity_lookup(session: AsyncSession) -> None:
    repository = CandidateRepository()
    candidate = await repository.create(
        session,
        data=data(
            "Demo Engineer",
            normalized_profile_url="https://www.linkedin.com/in/demo-engineer",
            profile_slug="Demo-Engineer",
        ),
    )
    assert (
        await repository.get_by_normalized_profile_url(
            session, "https://www.linkedin.com/in/demo-engineer"
        )
        is candidate
    )
    assert await repository.get_by_linkedin_slug(session, "demo-engineer") is candidate


async def test_list_filters_sort_and_counts(session: AsyncSession) -> None:
    repository = CandidateRepository()
    first = await repository.create(
        session,
        data=data(
            "Alpha Engineer",
            city="Bursa",
            current_title="Backend Engineer",
            data_quality_score=80,
            total_experience_months=60,
        ),
    )
    await repository.create(session, data=data("Beta Engineer", city="Istanbul"))
    session.add(
        CandidateExperience(
            candidate_id=first.id,
            position_title_raw="Engineer",
            confidence=1,
            sort_order=0,
        )
    )
    await session.flush()
    records = await repository.list(
        session,
        offset=0,
        limit=10,
        filters=CandidateListFilters(
            city="bursa",
            search="backend",
            min_data_quality=70,
            min_experience_months=50,
        ),
        sort=CandidateSort(CandidateSortField.DATA_QUALITY_SCORE, SortDirection.DESC),
    )
    assert len(records) == 1
    assert records[0].candidate is first
    assert records[0].experience_count == 1
    assert await repository.count(session, filters=CandidateListFilters(city="Bursa")) == 1


async def _result(session: AsyncSession) -> SearchResult:
    job = await JobRepository().create(
        session,
        data={
            "source": JobSource.MANUAL,
            "company_name": "Demo Company",
            "title": "Engineer",
            "description_raw": "Build systems",
        },
    )
    query = SearchQuery(
        job_id=job.id,
        source=SearchSource.GOOGLE_XRAY,
        language=SearchLanguage.EN,
        query_text="demo",
        normalized_query_key="demo",
    )
    session.add(query)
    await session.flush()
    result = SearchResult(
        search_query_id=query.id,
        source_url="https://example.com/person",
        normalized_url="https://example.com/person",
    )
    session.add(result)
    await session.flush()
    return result


async def test_attach_list_move_and_delete_nulls_result(session: AsyncSession) -> None:
    repository = CandidateRepository()
    source = await repository.create(session, data=data("Source Candidate"))
    target = await repository.create(session, data=data("Target Candidate"))
    result = await _result(session)
    await repository.attach_search_result(session, result=result, candidate_id=source.id)
    assert (await repository.list_search_results(session, source.id)) == [result]
    assert (
        await repository.move_search_results(session, source_ids=[source.id], target_id=target.id)
        == 1
    )
    await session.refresh(result)
    assert result.candidate_id == target.id
    await repository.delete(session, candidate=target)
    await session.refresh(result)
    assert result.candidate_id is None


async def test_merge_audit_is_retained_when_target_deleted(session: AsyncSession) -> None:
    repository = CandidateRepository()
    candidate = await repository.create(session, data=data("Target Candidate"))
    audit = await repository.create_merge_audit(
        session,
        data={
            "target_candidate_id": candidate.id,
            "source_candidate_ids": ["source-id"],
            "field_strategy": "keep_target",
            "merged_fields": {},
            "conflicts": [],
            "moved_search_result_count": 0,
            "moved_experience_count": 0,
            "moved_education_count": 0,
            "moved_skill_count": 0,
            "moved_certification_count": 0,
            "moved_language_count": 0,
        },
    )
    await repository.delete(session, candidate=candidate)
    await session.refresh(audit)
    assert audit.target_candidate_id is None


async def test_relation_filters_bulk_attach_detach_and_empty_operations(
    session: AsyncSession,
) -> None:
    repository = CandidateRepository()
    candidate = await repository.create(
        session,
        data=data(
            "Filtered Candidate",
            normalized_profile_url="https://example.com/filtered",
        ),
    )
    session.add_all(
        [
            CandidateSkill(
                candidate_id=candidate.id,
                raw_name="Python",
                normalized_name="python",
                source=CandidateSkillSource.MANUAL,
                confidence=1,
            ),
            CandidateEducation(
                candidate_id=candidate.id,
                institution_name="Demo University",
                field_of_study_normalized="computer engineering",
            ),
        ]
    )
    result = await _result(session)
    assert (
        await repository.attach_search_results(
            session, result_ids=[result.id], candidate_id=candidate.id
        )
        == 1
    )
    filters = CandidateListFilters(
        has_profile_url=True,
        has_search_results=True,
        skill="Python",
        education_field="Computer Engineering",
    )
    listed = await repository.list(
        session,
        offset=0,
        limit=10,
        filters=filters,
        sort=CandidateSort(CandidateSortField.FULL_NAME, SortDirection.ASC),
    )
    assert [record.candidate.id for record in listed] == [candidate.id]
    await repository.detach_search_result(session, result.id)
    await session.refresh(result)
    assert result.candidate_id is None
    assert (
        await repository.attach_search_results(session, result_ids=[], candidate_id=candidate.id)
        == 0
    )
    assert await repository.move_search_results(session, source_ids=[], target_id=candidate.id) == 0
    assert await repository.list_by_ids(session, []) == []
    assert await repository.delete_candidates(session, []) == 0


async def test_duplicate_lookup_without_identity_is_empty(session: AsyncSession) -> None:
    repository = CandidateRepository()
    candidate = await repository.create(
        session,
        data={"source": CandidateSource.MANUAL, "discovery_title": "Only title"},
    )
    assert await repository.find_duplicate_candidates(session, candidate) == []
