from sqlalchemy import CheckConstraint, UniqueConstraint

from app.db.base import Base
from app.db.models import JobPosting, JobRequirement, SearchQuery, SearchResult


def constraint_names(table_name: str, constraint_type: type) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {
        str(constraint.name)
        for constraint in table.constraints
        if isinstance(constraint, constraint_type)
    }


def test_job_and_search_tables_are_registered() -> None:
    assert {JobPosting.__tablename__, JobRequirement.__tablename__} <= Base.metadata.tables.keys()
    assert {SearchQuery.__tablename__, SearchResult.__tablename__} <= Base.metadata.tables.keys()


def test_job_and_search_constraints_are_registered() -> None:
    assert "ck_job_postings_experience_range_valid" in constraint_names(
        "job_postings", CheckConstraint
    )
    assert "ck_job_requirements_confidence_range" in constraint_names(
        "job_requirements", CheckConstraint
    )
    assert "ck_search_queries_precision_level_range" in constraint_names(
        "search_queries", CheckConstraint
    )
    assert "uq_search_result_query_url" in constraint_names("search_results", UniqueConstraint)
