"""create_initial_domain_models

Revision ID: fcb788e29200
Revises:
Create Date: 2026-07-13 13:21:13.715861
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "fcb788e29200"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("primary_profile_url", sa.String(length=2048), nullable=True),
        sa.Column("normalized_profile_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "google_xray",
                "professional_network",
                "manual",
                "imported",
                "demo",
                name="candidate_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("headline", sa.String(length=1000), nullable=True),
        sa.Column("about", sa.Text(), nullable=True),
        sa.Column("location_raw", sa.String(length=500), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("current_title", sa.String(length=255), nullable=True),
        sa.Column("current_company", sa.String(length=255), nullable=True),
        sa.Column("total_experience_months", sa.Integer(), nullable=True),
        sa.Column("open_to_work", sa.Boolean(), nullable=True),
        sa.Column(
            "profile_status",
            sa.Enum(
                "discovered",
                "queued",
                "scraped",
                "partial",
                "unavailable",
                "failed",
                name="candidate_profile_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("data_quality_score", sa.Float(), nullable=False),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "data_quality_score >= 0 AND data_quality_score <= 100",
            name=op.f("ck_candidates_data_quality_score_range"),
        ),
        sa.CheckConstraint(
            "total_experience_months IS NULL OR total_experience_months >= 0",
            name=op.f("ck_candidates_total_experience_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidates")),
    )
    op.create_index(op.f("ix_candidates_city"), "candidates", ["city"], unique=False)
    op.create_index("ix_candidates_created_at", "candidates", ["created_at"], unique=False)
    op.create_index(
        op.f("ix_candidates_current_company"), "candidates", ["current_company"], unique=False
    )
    op.create_index(
        op.f("ix_candidates_current_title"), "candidates", ["current_title"], unique=False
    )
    op.create_index(
        op.f("ix_candidates_data_quality_score"), "candidates", ["data_quality_score"], unique=False
    )
    op.create_index(op.f("ix_candidates_full_name"), "candidates", ["full_name"], unique=False)
    op.create_index(
        op.f("ix_candidates_normalized_profile_url"),
        "candidates",
        ["normalized_profile_url"],
        unique=True,
    )
    op.create_index(
        op.f("ix_candidates_profile_status"), "candidates", ["profile_status"], unique=False
    )
    op.create_index(op.f("ix_candidates_source"), "candidates", ["source"], unique=False)
    op.create_table(
        "job_postings",
        sa.Column(
            "source",
            sa.Enum(
                "manual",
                "kariyer_net",
                "linkedin",
                "other",
                name="job_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description_raw", sa.Text(), nullable=False),
        sa.Column("description_clean", sa.Text(), nullable=True),
        sa.Column("location_raw", sa.String(length=500), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("employment_type", sa.String(length=120), nullable=True),
        sa.Column("seniority_level", sa.String(length=120), nullable=True),
        sa.Column("min_experience_years", sa.Float(), nullable=True),
        sa.Column("max_experience_years", sa.Float(), nullable=True),
        sa.Column(
            "education_requirements",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "required_skills",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "preferred_skills",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "languages",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "certifications",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "keywords_tr",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "keywords_en",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "parsed",
                "sourcing",
                "completed",
                "archived",
                name="job_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "max_experience_years >= 0", name=op.f("ck_job_postings_max_experience_nonnegative")
        ),
        sa.CheckConstraint(
            "max_experience_years IS NULL OR min_experience_years IS NULL "
            "OR max_experience_years >= min_experience_years",
            name=op.f("ck_job_postings_experience_range_valid"),
        ),
        sa.CheckConstraint(
            "min_experience_years >= 0", name=op.f("ck_job_postings_min_experience_nonnegative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_postings")),
    )
    op.create_index(op.f("ix_job_postings_city"), "job_postings", ["city"], unique=False)
    op.create_index(
        op.f("ix_job_postings_company_name"), "job_postings", ["company_name"], unique=False
    )
    op.create_index("ix_job_postings_created_at", "job_postings", ["created_at"], unique=False)
    op.create_index(op.f("ix_job_postings_source"), "job_postings", ["source"], unique=False)
    op.create_index(op.f("ix_job_postings_status"), "job_postings", ["status"], unique=False)
    op.create_index(op.f("ix_job_postings_title"), "job_postings", ["title"], unique=False)
    op.create_table(
        "background_tasks",
        sa.Column(
            "type",
            sa.Enum(
                "parse_job",
                "generate_queries",
                "execute_search",
                "import_search_results",
                "scrape_profile_fast",
                "scrape_profile_deep",
                "match_candidate",
                "match_all_candidates",
                name="background_task_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "failed",
                "cancelled",
                name="background_task_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("current_step", sa.String(length=255), nullable=True),
        sa.Column("completed_items", sa.Integer(), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=True),
        sa.Column("percentage", sa.Float(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "result",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "completed_items >= 0", name=op.f("ck_background_tasks_completed_items_nonnegative")
        ),
        sa.CheckConstraint(
            "percentage >= 0 AND percentage <= 100",
            name=op.f("ck_background_tasks_percentage_range"),
        ),
        sa.CheckConstraint(
            "total_items IS NULL OR completed_items <= total_items",
            name=op.f("ck_background_tasks_completed_within_total"),
        ),
        sa.CheckConstraint(
            "total_items IS NULL OR total_items >= 0",
            name=op.f("ck_background_tasks_total_items_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_background_tasks_candidate_id_candidates"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job_postings.id"],
            name=op.f("fk_background_tasks_job_id_job_postings"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_background_tasks")),
    )
    op.create_index(
        op.f("ix_background_tasks_candidate_id"), "background_tasks", ["candidate_id"], unique=False
    )
    op.create_index(
        "ix_background_tasks_created_at", "background_tasks", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_background_tasks_job_id"), "background_tasks", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_background_tasks_status"), "background_tasks", ["status"], unique=False
    )
    op.create_index(op.f("ix_background_tasks_type"), "background_tasks", ["type"], unique=False)
    op.create_table(
        "candidate_certifications",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("issuer", sa.String(length=255), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("credential_id", sa.String(length=255), nullable=True),
        sa.Column("credential_url", sa.String(length=2048), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "expiration_date IS NULL OR issue_date IS NULL OR expiration_date >= issue_date",
            name=op.f("ck_candidate_certifications_date_range_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_candidate_certifications_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_certifications")),
    )
    op.create_index(
        op.f("ix_candidate_certifications_candidate_id"),
        "candidate_certifications",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_certifications_issuer"),
        "candidate_certifications",
        ["issuer"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_certifications_name"), "candidate_certifications", ["name"], unique=False
    )
    op.create_table(
        "candidate_educations",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("institution_name", sa.String(length=500), nullable=False),
        sa.Column("degree", sa.String(length=255), nullable=True),
        sa.Column("field_of_study", sa.String(length=255), nullable=True),
        sa.Column("field_of_study_normalized", sa.String(length=255), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("grade", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_candidate_educations_confidence_range"),
        ),
        sa.CheckConstraint(
            "end_year IS NULL OR end_year BETWEEN 1900 AND 2100",
            name=op.f("ck_candidate_educations_end_year_range"),
        ),
        sa.CheckConstraint(
            "end_year IS NULL OR start_year IS NULL OR end_year >= start_year",
            name=op.f("ck_candidate_educations_year_range_valid"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_candidate_educations_sort_order_nonnegative")
        ),
        sa.CheckConstraint(
            "start_year IS NULL OR start_year BETWEEN 1900 AND 2100",
            name=op.f("ck_candidate_educations_start_year_range"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_candidate_educations_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_educations")),
    )
    op.create_index(
        op.f("ix_candidate_educations_candidate_id"),
        "candidate_educations",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_educations_end_year"), "candidate_educations", ["end_year"], unique=False
    )
    op.create_index(
        op.f("ix_candidate_educations_field_of_study_normalized"),
        "candidate_educations",
        ["field_of_study_normalized"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_educations_institution_name"),
        "candidate_educations",
        ["institution_name"],
        unique=False,
    )
    op.create_table(
        "candidate_experiences",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("position_title_raw", sa.String(length=500), nullable=False),
        sa.Column("position_title_normalized", sa.String(length=255), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("company_url", sa.String(length=2048), nullable=True),
        sa.Column("employment_type", sa.String(length=120), nullable=True),
        sa.Column("location", sa.String(length=500), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "skills_detected",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("industry_detected", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_candidate_experiences_confidence_range"),
        ),
        sa.CheckConstraint(
            "duration_months IS NULL OR duration_months >= 0",
            name=op.f("ck_candidate_experiences_duration_months_nonnegative"),
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name=op.f("ck_candidate_experiences_date_range_valid"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_candidate_experiences_sort_order_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_candidate_experiences_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_experiences")),
    )
    op.create_index(
        op.f("ix_candidate_experiences_candidate_id"),
        "candidate_experiences",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_experiences_company_name"),
        "candidate_experiences",
        ["company_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_experiences_is_current"),
        "candidate_experiences",
        ["is_current"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_experiences_position_title_normalized"),
        "candidate_experiences",
        ["position_title_normalized"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_experiences_start_date"),
        "candidate_experiences",
        ["start_date"],
        unique=False,
    )
    op.create_table(
        "candidate_languages",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("language", sa.String(length=120), nullable=False),
        sa.Column("language_normalized", sa.String(length=120), nullable=False),
        sa.Column("proficiency", sa.String(length=120), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_candidate_languages_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_candidate_languages_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_languages")),
        sa.UniqueConstraint("candidate_id", "language_normalized", name="uq_candidate_language"),
    )
    op.create_index(
        op.f("ix_candidate_languages_candidate_id"),
        "candidate_languages",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_languages_language_normalized"),
        "candidate_languages",
        ["language_normalized"],
        unique=False,
    )
    op.create_table(
        "candidate_matches",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("title_score", sa.Float(), nullable=False),
        sa.Column("skill_score", sa.Float(), nullable=False),
        sa.Column("experience_score", sa.Float(), nullable=False),
        sa.Column("industry_score", sa.Float(), nullable=False),
        sa.Column("education_score", sa.Float(), nullable=False),
        sa.Column("location_score", sa.Float(), nullable=False),
        sa.Column("language_score", sa.Float(), nullable=False),
        sa.Column("certification_score", sa.Float(), nullable=False),
        sa.Column("semantic_score", sa.Float(), nullable=True),
        sa.Column(
            "matched_requirements",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "missing_requirements",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "uncertain_requirements",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("score_version", sa.String(length=50), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "certification_score IS NULL OR "
            "(certification_score >= 0 AND certification_score <= 100)",
            name=op.f("ck_candidate_matches_certification_score_range"),
        ),
        sa.CheckConstraint(
            "education_score IS NULL OR (education_score >= 0 AND education_score <= 100)",
            name=op.f("ck_candidate_matches_education_score_range"),
        ),
        sa.CheckConstraint(
            "experience_score IS NULL OR (experience_score >= 0 AND experience_score <= 100)",
            name=op.f("ck_candidate_matches_experience_score_range"),
        ),
        sa.CheckConstraint(
            "industry_score IS NULL OR (industry_score >= 0 AND industry_score <= 100)",
            name=op.f("ck_candidate_matches_industry_score_range"),
        ),
        sa.CheckConstraint(
            "language_score IS NULL OR (language_score >= 0 AND language_score <= 100)",
            name=op.f("ck_candidate_matches_language_score_range"),
        ),
        sa.CheckConstraint(
            "location_score IS NULL OR (location_score >= 0 AND location_score <= 100)",
            name=op.f("ck_candidate_matches_location_score_range"),
        ),
        sa.CheckConstraint(
            "semantic_score IS NULL OR (semantic_score >= 0 AND semantic_score <= 100)",
            name=op.f("ck_candidate_matches_semantic_score_range"),
        ),
        sa.CheckConstraint(
            "skill_score IS NULL OR (skill_score >= 0 AND skill_score <= 100)",
            name=op.f("ck_candidate_matches_skill_score_range"),
        ),
        sa.CheckConstraint(
            "title_score IS NULL OR (title_score >= 0 AND title_score <= 100)",
            name=op.f("ck_candidate_matches_title_score_range"),
        ),
        sa.CheckConstraint(
            "total_score IS NULL OR (total_score >= 0 AND total_score <= 100)",
            name=op.f("ck_candidate_matches_total_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_candidate_matches_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job_postings.id"],
            name=op.f("fk_candidate_matches_job_id_job_postings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_matches")),
        sa.UniqueConstraint("job_id", "candidate_id", name="uq_candidate_match_job_candidate"),
    )
    op.create_index(
        op.f("ix_candidate_matches_candidate_id"),
        "candidate_matches",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_matches_created_at", "candidate_matches", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_candidate_matches_job_id"), "candidate_matches", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_candidate_matches_total_score"), "candidate_matches", ["total_score"], unique=False
    )
    op.create_table(
        "candidate_skills",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("raw_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("endorsement_count", sa.Integer(), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "profile_skill",
                "experience_text",
                "about_text",
                "inferred",
                "manual",
                name="candidate_skill_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_candidate_skills_confidence_range")
        ),
        sa.CheckConstraint(
            "endorsement_count IS NULL OR endorsement_count >= 0",
            name=op.f("ck_candidate_skills_endorsement_count_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_candidate_skills_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_skills")),
        sa.UniqueConstraint(
            "candidate_id", "normalized_name", "source", name="uq_candidate_skill_source"
        ),
    )
    op.create_index(
        op.f("ix_candidate_skills_candidate_id"), "candidate_skills", ["candidate_id"], unique=False
    )
    op.create_index(
        op.f("ix_candidate_skills_category"), "candidate_skills", ["category"], unique=False
    )
    op.create_index(
        op.f("ix_candidate_skills_normalized_name"),
        "candidate_skills",
        ["normalized_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_candidate_skills_source"), "candidate_skills", ["source"], unique=False
    )
    op.create_table(
        "job_requirements",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "title",
                "skill",
                "education",
                "experience",
                "location",
                "language",
                "certification",
                "industry",
                name="requirement_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("raw_value", sa.String(length=1000), nullable=False),
        sa.Column("normalized_value", sa.String(length=500), nullable=False),
        sa.Column(
            "importance",
            sa.Enum(
                "required",
                "preferred",
                "optional",
                name="requirement_importance",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "rule",
                "ai",
                "manual",
                name="requirement_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_job_requirements_confidence_range")
        ),
        sa.CheckConstraint("weight >= 0", name=op.f("ck_job_requirements_weight_nonnegative")),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job_postings.id"],
            name=op.f("fk_job_requirements_job_id_job_postings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_requirements")),
    )
    op.create_index(
        op.f("ix_job_requirements_importance"), "job_requirements", ["importance"], unique=False
    )
    op.create_index(
        op.f("ix_job_requirements_job_id"), "job_requirements", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_job_requirements_normalized_value"),
        "job_requirements",
        ["normalized_value"],
        unique=False,
    )
    op.create_index(op.f("ix_job_requirements_type"), "job_requirements", ["type"], unique=False)
    op.create_table(
        "search_queries",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "google_xray",
                "manual",
                "professional_network",
                name="search_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "language",
            sa.Enum("tr", "en", name="search_language", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("query_type", sa.String(length=100), nullable=True),
        sa.Column("precision_level", sa.Integer(), nullable=True),
        sa.Column("expected_intent", sa.String(length=255), nullable=True),
        sa.Column(
            "included_titles",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "included_skills",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "included_locations",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "ready",
                "running",
                "completed",
                "failed",
                name="search_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "precision_level IS NULL OR precision_level BETWEEN 1 AND 5",
            name=op.f("ck_search_queries_precision_level_range"),
        ),
        sa.CheckConstraint(
            "result_count >= 0", name=op.f("ck_search_queries_result_count_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job_postings.id"],
            name=op.f("fk_search_queries_job_id_job_postings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_queries")),
    )
    op.create_index("ix_search_queries_created_at", "search_queries", ["created_at"], unique=False)
    op.create_index(op.f("ix_search_queries_job_id"), "search_queries", ["job_id"], unique=False)
    op.create_index(
        op.f("ix_search_queries_language"), "search_queries", ["language"], unique=False
    )
    op.create_index(op.f("ix_search_queries_source"), "search_queries", ["source"], unique=False)
    op.create_index(op.f("ix_search_queries_status"), "search_queries", ["status"], unique=False)
    op.create_table(
        "shortlist_entries",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "shortlisted",
                "reviewed",
                "rejected",
                "contacted",
                name="shortlist_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("recruiter_note", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_shortlist_entries_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job_postings.id"],
            name=op.f("fk_shortlist_entries_job_id_job_postings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shortlist_entries")),
        sa.UniqueConstraint("job_id", "candidate_id", name="uq_shortlist_job_candidate"),
    )
    op.create_index(
        op.f("ix_shortlist_entries_candidate_id"),
        "shortlist_entries",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_shortlist_entries_created_at", "shortlist_entries", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_shortlist_entries_job_id"), "shortlist_entries", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_shortlist_entries_status"), "shortlist_entries", ["status"], unique=False
    )
    op.create_table(
        "search_results",
        sa.Column("search_query_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("normalized_url", sa.String(length=2048), nullable=False),
        sa.Column("source_domain", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=1000), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("displayed_name", sa.String(length=255), nullable=True),
        sa.Column("displayed_headline", sa.String(length=1000), nullable=True),
        sa.Column("displayed_location", sa.String(length=500), nullable=True),
        sa.Column("result_rank", sa.Integer(), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False),
        sa.Column("duplicate_of_id", sa.Uuid(), nullable=True),
        sa.Column("pre_score", sa.Float(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "pre_score IS NULL OR (pre_score >= 0 AND pre_score <= 100)",
            name=op.f("ck_search_results_pre_score_range"),
        ),
        sa.CheckConstraint(
            "result_rank IS NULL OR result_rank >= 1",
            name=op.f("ck_search_results_result_rank_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_search_results_candidate_id_candidates"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_id"],
            ["search_results.id"],
            name=op.f("fk_search_results_duplicate_of_id_search_results"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["search_query_id"],
            ["search_queries.id"],
            name=op.f("fk_search_results_search_query_id_search_queries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_results")),
        sa.UniqueConstraint("search_query_id", "normalized_url", name="uq_search_result_query_url"),
    )
    op.create_index(
        op.f("ix_search_results_candidate_id"), "search_results", ["candidate_id"], unique=False
    )
    op.create_index(
        op.f("ix_search_results_discovered_at"), "search_results", ["discovered_at"], unique=False
    )
    op.create_index(
        op.f("ix_search_results_duplicate_of_id"),
        "search_results",
        ["duplicate_of_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_results_is_duplicate"), "search_results", ["is_duplicate"], unique=False
    )
    op.create_index(
        op.f("ix_search_results_normalized_url"), "search_results", ["normalized_url"], unique=False
    )
    op.create_index(
        op.f("ix_search_results_pre_score"), "search_results", ["pre_score"], unique=False
    )
    op.create_index(
        op.f("ix_search_results_search_query_id"),
        "search_results",
        ["search_query_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_results_source_domain"), "search_results", ["source_domain"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_search_results_source_domain"), table_name="search_results")
    op.drop_index(op.f("ix_search_results_search_query_id"), table_name="search_results")
    op.drop_index(op.f("ix_search_results_pre_score"), table_name="search_results")
    op.drop_index(op.f("ix_search_results_normalized_url"), table_name="search_results")
    op.drop_index(op.f("ix_search_results_is_duplicate"), table_name="search_results")
    op.drop_index(op.f("ix_search_results_duplicate_of_id"), table_name="search_results")
    op.drop_index(op.f("ix_search_results_discovered_at"), table_name="search_results")
    op.drop_index(op.f("ix_search_results_candidate_id"), table_name="search_results")
    op.drop_table("search_results")
    op.drop_index(op.f("ix_shortlist_entries_status"), table_name="shortlist_entries")
    op.drop_index(op.f("ix_shortlist_entries_job_id"), table_name="shortlist_entries")
    op.drop_index("ix_shortlist_entries_created_at", table_name="shortlist_entries")
    op.drop_index(op.f("ix_shortlist_entries_candidate_id"), table_name="shortlist_entries")
    op.drop_table("shortlist_entries")
    op.drop_index(op.f("ix_search_queries_status"), table_name="search_queries")
    op.drop_index(op.f("ix_search_queries_source"), table_name="search_queries")
    op.drop_index(op.f("ix_search_queries_language"), table_name="search_queries")
    op.drop_index(op.f("ix_search_queries_job_id"), table_name="search_queries")
    op.drop_index("ix_search_queries_created_at", table_name="search_queries")
    op.drop_table("search_queries")
    op.drop_index(op.f("ix_job_requirements_type"), table_name="job_requirements")
    op.drop_index(op.f("ix_job_requirements_normalized_value"), table_name="job_requirements")
    op.drop_index(op.f("ix_job_requirements_job_id"), table_name="job_requirements")
    op.drop_index(op.f("ix_job_requirements_importance"), table_name="job_requirements")
    op.drop_table("job_requirements")
    op.drop_index(op.f("ix_candidate_skills_source"), table_name="candidate_skills")
    op.drop_index(op.f("ix_candidate_skills_normalized_name"), table_name="candidate_skills")
    op.drop_index(op.f("ix_candidate_skills_category"), table_name="candidate_skills")
    op.drop_index(op.f("ix_candidate_skills_candidate_id"), table_name="candidate_skills")
    op.drop_table("candidate_skills")
    op.drop_index(op.f("ix_candidate_matches_total_score"), table_name="candidate_matches")
    op.drop_index(op.f("ix_candidate_matches_job_id"), table_name="candidate_matches")
    op.drop_index("ix_candidate_matches_created_at", table_name="candidate_matches")
    op.drop_index(op.f("ix_candidate_matches_candidate_id"), table_name="candidate_matches")
    op.drop_table("candidate_matches")
    op.drop_index(
        op.f("ix_candidate_languages_language_normalized"), table_name="candidate_languages"
    )
    op.drop_index(op.f("ix_candidate_languages_candidate_id"), table_name="candidate_languages")
    op.drop_table("candidate_languages")
    op.drop_index(op.f("ix_candidate_experiences_start_date"), table_name="candidate_experiences")
    op.drop_index(
        op.f("ix_candidate_experiences_position_title_normalized"),
        table_name="candidate_experiences",
    )
    op.drop_index(op.f("ix_candidate_experiences_is_current"), table_name="candidate_experiences")
    op.drop_index(op.f("ix_candidate_experiences_company_name"), table_name="candidate_experiences")
    op.drop_index(op.f("ix_candidate_experiences_candidate_id"), table_name="candidate_experiences")
    op.drop_table("candidate_experiences")
    op.drop_index(
        op.f("ix_candidate_educations_institution_name"), table_name="candidate_educations"
    )
    op.drop_index(
        op.f("ix_candidate_educations_field_of_study_normalized"), table_name="candidate_educations"
    )
    op.drop_index(op.f("ix_candidate_educations_end_year"), table_name="candidate_educations")
    op.drop_index(op.f("ix_candidate_educations_candidate_id"), table_name="candidate_educations")
    op.drop_table("candidate_educations")
    op.drop_index(op.f("ix_candidate_certifications_name"), table_name="candidate_certifications")
    op.drop_index(op.f("ix_candidate_certifications_issuer"), table_name="candidate_certifications")
    op.drop_index(
        op.f("ix_candidate_certifications_candidate_id"), table_name="candidate_certifications"
    )
    op.drop_table("candidate_certifications")
    op.drop_index(op.f("ix_background_tasks_type"), table_name="background_tasks")
    op.drop_index(op.f("ix_background_tasks_status"), table_name="background_tasks")
    op.drop_index(op.f("ix_background_tasks_job_id"), table_name="background_tasks")
    op.drop_index("ix_background_tasks_created_at", table_name="background_tasks")
    op.drop_index(op.f("ix_background_tasks_candidate_id"), table_name="background_tasks")
    op.drop_table("background_tasks")
    op.drop_index(op.f("ix_job_postings_title"), table_name="job_postings")
    op.drop_index(op.f("ix_job_postings_status"), table_name="job_postings")
    op.drop_index(op.f("ix_job_postings_source"), table_name="job_postings")
    op.drop_index("ix_job_postings_created_at", table_name="job_postings")
    op.drop_index(op.f("ix_job_postings_company_name"), table_name="job_postings")
    op.drop_index(op.f("ix_job_postings_city"), table_name="job_postings")
    op.drop_table("job_postings")
    op.drop_index(op.f("ix_candidates_source"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_profile_status"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_normalized_profile_url"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_full_name"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_data_quality_score"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_current_title"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_current_company"), table_name="candidates")
    op.drop_index("ix_candidates_created_at", table_name="candidates")
    op.drop_index(op.f("ix_candidates_city"), table_name="candidates")
    op.drop_table("candidates")
