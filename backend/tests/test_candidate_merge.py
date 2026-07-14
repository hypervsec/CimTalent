from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError
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
from app.domain.candidates import (
    CandidateMergeConflictError,
    CandidateMergeError,
    CandidateNotFoundError,
)
from app.domain.candidates.types import CandidateFieldStrategy
from app.repositories.candidates import CandidateRepository
from app.repositories.jobs import JobRepository
from app.services.candidates import CandidateService


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


async def candidates(
    session: AsyncSession,
) -> tuple[CandidateRepository, Candidate, Candidate]:
    repository = CandidateRepository()
    target = await repository.create(
        session,
        data={
            "source": CandidateSource.MANUAL,
            "full_name": "Target Candidate",
            "data_quality_score": 15,
        },
    )
    source = await repository.create(
        session,
        data={
            "source": CandidateSource.IMPORTED,
            "full_name": "Source Candidate",
            "headline": "Backend Engineer",
            "data_quality_score": 25,
        },
    )
    return repository, target, source


async def add_conflicting_children(
    session: AsyncSession, target_id: UUID, source_id: UUID
) -> SearchResult:
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
        source=SearchSource.MANUAL,
        language=SearchLanguage.EN,
        query_text="candidate",
        normalized_query_key="candidate",
    )
    session.add(query)
    await session.flush()
    result = SearchResult(
        search_query_id=query.id,
        candidate_id=source_id,
        source_url="https://example.com/source",
        normalized_url="https://example.com/source",
    )
    session.add_all(
        [
            result,
            CandidateExperience(
                candidate_id=source_id,
                position_title_raw="Engineer",
                confidence=1,
                sort_order=0,
            ),
            CandidateEducation(candidate_id=source_id, institution_name="Demo University"),
            CandidateCertification(candidate_id=source_id, name="Demo Certificate"),
            CandidateSkill(
                candidate_id=target_id,
                raw_name="Python",
                normalized_name="python",
                source=CandidateSkillSource.MANUAL,
                confidence=0.8,
            ),
            CandidateSkill(
                candidate_id=source_id,
                raw_name="Python",
                normalized_name="python",
                source=CandidateSkillSource.MANUAL,
                confidence=1,
            ),
            CandidateLanguage(
                candidate_id=target_id,
                language="English",
                language_normalized="english",
                confidence=0.8,
            ),
            CandidateLanguage(
                candidate_id=source_id,
                language="English",
                language_normalized="english",
                proficiency="Professional",
                confidence=1,
            ),
            _match(job.id, target_id, "Target explanation"),
            _match(job.id, source_id, "Source explanation"),
            ShortlistEntry(job_id=job.id, candidate_id=target_id, recruiter_note="Target note"),
            ShortlistEntry(job_id=job.id, candidate_id=source_id, recruiter_note="Source note"),
        ]
    )
    await session.flush()
    return result


def _match(job_id: UUID, candidate_id: UUID, explanation: str) -> CandidateMatch:
    return CandidateMatch(
        job_id=job_id,
        candidate_id=candidate_id,
        total_score=50,
        title_score=50,
        skill_score=50,
        experience_score=50,
        industry_score=50,
        education_score=50,
        location_score=50,
        language_score=50,
        certification_score=50,
        explanation=explanation,
        score_version="v1",
    )


async def test_merge_moves_children_consolidates_conflicts_and_audits(
    session: AsyncSession,
) -> None:
    repository, target, source = await candidates(session)
    result = await add_conflicting_children(session, target.id, source.id)
    await session.commit()
    service = CandidateService(repository)

    outcome = await service.merge_candidates(
        session,
        target.id,
        source_candidate_ids=[source.id],
        field_strategy=CandidateFieldStrategy.KEEP_TARGET,
        explicit_field_values=None,
        dry_run=False,
    )

    assert outcome.candidate is not None
    assert outcome.candidate.candidate.full_name == "Target Candidate"
    assert outcome.candidate.candidate.headline == "Backend Engineer"
    assert outcome.candidate.experience_count == 1
    assert outcome.candidate.education_count == 1
    assert outcome.candidate.certification_count == 1
    assert outcome.candidate.skill_count == 1
    assert outcome.candidate.language_count == 1
    assert outcome.moved_counts == {
        "search_results": 1,
        "experiences": 1,
        "educations": 1,
        "skills": 1,
        "certifications": 1,
        "languages": 1,
    }
    assert "duplicate_skills_consolidated" in outcome.warnings
    assert "shortlist_conflicts_consolidated_without_note_loss" in outcome.warnings
    assert await repository.get_by_id(session, source.id) is None
    await session.refresh(result)
    assert result.candidate_id == target.id

    match = await session.scalar(
        select(CandidateMatch).where(CandidateMatch.candidate_id == target.id)
    )
    shortlist = await session.scalar(
        select(ShortlistEntry).where(ShortlistEntry.candidate_id == target.id)
    )
    assert match is not None and "Target explanation" in (match.explanation or "")
    assert "Source explanation" in (match.explanation or "")
    assert shortlist is not None and "Target note" in (shortlist.recruiter_note or "")
    assert "Source note" in (shortlist.recruiter_note or "")
    audit = await session.scalar(select(CandidateMergeAudit))
    assert audit is not None
    assert audit.target_candidate_id == target.id
    assert audit.source_candidate_ids == [str(source.id)]


async def test_merge_dry_run_and_prefer_newest_do_not_mutate(session: AsyncSession) -> None:
    repository, target, source = await candidates(session)
    source.updated_at = target.updated_at.replace(year=target.updated_at.year + 1)
    await session.flush()
    outcome = await CandidateService(repository).merge_candidates(
        session,
        target.id,
        source_candidate_ids=[source.id],
        field_strategy=CandidateFieldStrategy.PREFER_NEWEST,
        explicit_field_values=None,
        dry_run=True,
    )
    assert outcome.merged_fields["full_name"] == "Source Candidate"
    assert await repository.exists(session, source.id)
    assert await session.scalar(select(func.count(CandidateMergeAudit.id))) == 0


async def test_merge_validation(session: AsyncSession) -> None:
    repository, target, source = await candidates(session)
    service = CandidateService(repository)
    with pytest.raises(CandidateMergeConflictError):
        await service.merge_candidates(
            session,
            target.id,
            source_candidate_ids=[target.id],
            field_strategy=CandidateFieldStrategy.KEEP_TARGET,
            explicit_field_values=None,
            dry_run=False,
        )
    with pytest.raises(CandidateMergeConflictError):
        await service.merge_candidates(
            session,
            target.id,
            source_candidate_ids=[source.id, source.id],
            field_strategy=CandidateFieldStrategy.KEEP_TARGET,
            explicit_field_values=None,
            dry_run=False,
        )
    with pytest.raises(CandidateNotFoundError):
        await service.merge_candidates(
            session,
            target.id,
            source_candidate_ids=[uuid4()],
            field_strategy=CandidateFieldStrategy.KEEP_TARGET,
            explicit_field_values=None,
            dry_run=False,
        )


async def test_merge_rollback_restores_links(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, target, source = await candidates(session)
    result = await add_conflicting_children(session, target.id, source.id)
    target_id = target.id
    source_id = source.id
    result_id = result.id
    await session.commit()

    async def fail_delete(_session: AsyncSession, candidate_ids: object) -> int:
        raise SQLAlchemyError("forced merge failure")

    monkeypatch.setattr(repository, "delete_candidates", fail_delete)
    with pytest.raises(CandidateMergeError):
        await CandidateService(repository).merge_candidates(
            session,
            target_id,
            source_candidate_ids=[source_id],
            field_strategy=CandidateFieldStrategy.KEEP_TARGET,
            explicit_field_values=None,
            dry_run=False,
        )
    assert await repository.exists(session, source_id)
    restored_result = await session.get(SearchResult, result_id)
    assert restored_result is not None and restored_result.candidate_id == source_id
    assert await session.scalar(select(func.count(CandidateMergeAudit.id))) == 0
