from sqlalchemy import CheckConstraint, UniqueConstraint

from app.db.base import Base
from app.db.models import (
    Candidate,
    CandidateCertification,
    CandidateEducation,
    CandidateEnrichmentRun,
    CandidateExperience,
    CandidateLanguage,
    CandidateSkill,
)


def named_constraints(table_name: str, kind: type) -> set[str]:
    return {
        str(constraint.name)
        for constraint in Base.metadata.tables[table_name].constraints
        if isinstance(constraint, kind)
    }


def test_candidate_tables_are_registered() -> None:
    expected = {
        Candidate.__tablename__,
        CandidateExperience.__tablename__,
        CandidateEducation.__tablename__,
        CandidateEnrichmentRun.__tablename__,
        CandidateSkill.__tablename__,
        CandidateCertification.__tablename__,
        CandidateLanguage.__tablename__,
    }
    assert expected <= Base.metadata.tables.keys()


def test_candidate_unique_constraints_are_registered() -> None:
    assert "uq_candidate_skill_source" in named_constraints("candidate_skills", UniqueConstraint)
    assert "uq_candidate_language" in named_constraints("candidate_languages", UniqueConstraint)


def test_candidate_confidence_constraints_are_registered() -> None:
    for table_name in (
        "candidate_experiences",
        "candidate_educations",
        "candidate_skills",
        "candidate_languages",
        "candidate_certifications",
    ):
        assert f"ck_{table_name}_confidence_range" in named_constraints(table_name, CheckConstraint)
