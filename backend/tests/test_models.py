from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, create_engine, event, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.enums import (
    BackgroundTaskStatus,
    BackgroundTaskType,
    CandidateSkillSource,
    CandidateSource,
    JobSource,
    RequirementImportance,
    RequirementSource,
    RequirementType,
    SearchLanguage,
    SearchSource,
)
from app.db.models import (
    BackgroundTask,
    Candidate,
    CandidateEducation,
    CandidateExperience,
    CandidateMatch,
    CandidateSkill,
    JobPosting,
    JobRequirement,
    SearchQuery,
    SearchResult,
    ShortlistEntry,
)

EXPECTED_TABLES = {
    "job_postings",
    "job_requirements",
    "search_queries",
    "search_results",
    "candidates",
    "candidate_experiences",
    "candidate_educations",
    "candidate_skills",
    "candidate_certifications",
    "candidate_languages",
    "candidate_matches",
    "candidate_merge_audits",
    "candidate_enrichment_runs",
    "shortlist_entries",
    "background_tasks",
}


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: Any, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    Base.metadata.drop_all(engine)
    engine.dispose()


def make_job() -> JobPosting:
    return JobPosting(
        source=JobSource.MANUAL,
        company_name="Example Industries",
        title="Software Developer",
        description_raw="Python and SQL",
    )


def make_candidate() -> Candidate:
    return Candidate(source=CandidateSource.DEMO, full_name="Demo Candidate")


def unique_names(table_name: str) -> set[str]:
    return {
        str(constraint.name)
        for constraint in Base.metadata.tables[table_name].constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_all_expected_tables_are_registered() -> None:
    assert Base.metadata.tables.keys() == EXPECTED_TABLES


def test_uuid_timestamps_defaults_and_mutable_json(session: Session) -> None:
    job = make_job()
    session.add(job)
    session.flush()

    assert job.id is not None
    assert job.created_at.tzinfo is not None
    assert job.required_skills == []

    job.required_skills.append("Python")
    assert session.is_modified(job, include_collections=True)


def test_job_requirement_cascades_on_job_delete(session: Session) -> None:
    job = make_job()
    job.requirements.append(
        JobRequirement(
            type=RequirementType.SKILL,
            raw_value="Python",
            normalized_value="python",
            importance=RequirementImportance.REQUIRED,
            source=RequirementSource.RULE,
        )
    )
    session.add(job)
    session.commit()
    requirement_id = job.requirements[0].id

    session.delete(job)
    session.commit()

    assert session.get(JobRequirement, requirement_id) is None


def test_search_query_result_relationship(session: Session) -> None:
    query = SearchQuery(
        job=make_job(),
        source=SearchSource.GOOGLE_XRAY,
        language=SearchLanguage.EN,
        query_text='"Software Developer" site:linkedin.com/in',
        normalized_query_key='"software developer" site:linkedin.com/in',
    )
    query.results.append(
        SearchResult(
            source_url="https://example.test/in/demo",
            normalized_url="https://example.test/in/demo",
        )
    )
    session.add(query)
    session.commit()

    assert query.results[0].search_query is query
    assert query.result_count == 0


def test_candidate_child_relationships_are_ordered(session: Session) -> None:
    candidate = make_candidate()
    candidate.experiences.extend(
        [
            CandidateExperience(position_title_raw="Senior Engineer", sort_order=2),
            CandidateExperience(position_title_raw="Engineer", sort_order=1),
        ]
    )
    candidate.educations.append(CandidateEducation(institution_name="Demo University"))
    candidate.skills.append(
        CandidateSkill(
            raw_name="Python",
            normalized_name="python",
            source=CandidateSkillSource.PROFILE_SKILL,
        )
    )
    session.add(candidate)
    session.commit()
    session.expire_all()

    loaded = session.scalars(select(Candidate).where(Candidate.id == candidate.id)).one()
    assert [item.sort_order for item in loaded.experiences] == [1, 2]
    assert loaded.experiences[0].candidate is loaded
    assert len(loaded.educations) == 1
    assert len(loaded.skills) == 1


def test_required_unique_constraints_exist() -> None:
    assert "uq_candidate_match_job_candidate" in unique_names("candidate_matches")
    assert "uq_shortlist_job_candidate" in unique_names("shortlist_entries")
    assert "uq_candidate_skill_source" in unique_names("candidate_skills")


def test_score_constraints_cover_every_match_score() -> None:
    names = {
        str(constraint.name)
        for constraint in Base.metadata.tables["candidate_matches"].constraints
        if isinstance(constraint, CheckConstraint)
    }
    score_columns = {
        "total_score",
        "title_score",
        "skill_score",
        "experience_score",
        "industry_score",
        "education_score",
        "location_score",
        "language_score",
        "certification_score",
        "semantic_score",
    }
    assert {f"ck_candidate_matches_{column}_range" for column in score_columns} <= names


def test_match_and_shortlist_relationships(session: Session) -> None:
    job = make_job()
    candidate = make_candidate()
    match = CandidateMatch(
        job=job,
        candidate=candidate,
        total_score=75,
        title_score=80,
        skill_score=70,
        experience_score=75,
        industry_score=60,
        education_score=80,
        location_score=100,
        language_score=50,
        certification_score=50,
        score_version="v1",
    )
    shortlist = ShortlistEntry(job=job, candidate=candidate)
    session.add_all([match, shortlist])
    session.commit()

    assert job.matches == [match]
    assert candidate.shortlist_entries == [shortlist]


def test_background_task_defaults_and_terminal_property(session: Session) -> None:
    task = BackgroundTask(type=BackgroundTaskType.PARSE_JOB)
    session.add(task)
    session.flush()

    assert task.status is BackgroundTaskStatus.PENDING
    assert task.completed_items == 0
    assert task.percentage == 0
    assert task.payload == {}
    assert task.result == {}
    assert task.is_terminal is False

    task.status = BackgroundTaskStatus.COMPLETED
    assert task.is_terminal is True
