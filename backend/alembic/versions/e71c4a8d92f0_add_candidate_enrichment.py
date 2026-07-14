"""add candidate enrichment persistence

Revision ID: e71c4a8d92f0
Revises: d9e4a6127b3c
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e71c4a8d92f0"
down_revision: str | None = "d9e4a6127b3c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("candidate_experiences", sa.Column("external_key", sa.String(500)))
    op.add_column("candidate_experiences", sa.Column("source", sa.String(120)))
    op.add_column("candidate_educations", sa.Column("external_key", sa.String(500)))
    op.add_column("candidate_educations", sa.Column("source", sa.String(120)))
    op.add_column("candidate_certifications", sa.Column("external_key", sa.String(500)))
    op.add_column("candidate_certifications", sa.Column("source", sa.String(120)))
    op.add_column(
        "candidate_certifications",
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
    )
    with op.batch_alter_table("candidate_certifications") as batch_op:
        batch_op.alter_column(
            "confidence", existing_type=sa.Float(), nullable=False, server_default=None
        )
    op.add_column("candidate_languages", sa.Column("source", sa.String(120)))
    op.create_index(
        "ix_candidate_experience_identity",
        "candidate_experiences",
        ["candidate_id", "source", "external_key"],
    )
    op.create_index(
        "ix_candidate_education_identity",
        "candidate_educations",
        ["candidate_id", "source", "external_key"],
    )
    op.create_index(
        "ix_candidate_certification_identity",
        "candidate_certifications",
        ["candidate_id", "source", "external_key"],
    )
    op.create_table(
        "candidate_enrichment_runs",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "manual",
                "linkedin",
                "imported",
                "demo",
                name="enrichment_provider",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.Enum("fast", "deep", name="enrichment_mode", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "partial",
                "failed",
                "cancelled",
                name="candidate_enrichment_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("parser_version", sa.String(100)),
        sa.Column("requested_sections", sa.JSON(), nullable=False),
        sa.Column("completed_sections", sa.JSON(), nullable=False),
        sa.Column("warning_codes", sa.JSON(), nullable=False),
        sa.Column("error_codes", sa.JSON(), nullable=False),
        sa.Column("input_summary", sa.JSON(), nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=False),
        sa.Column("data_quality_before", sa.Float(), nullable=False),
        sa.Column("data_quality_after", sa.Float()),
        *[
            sa.Column(f"{action}_{section}_count", sa.Integer(), nullable=False)
            for section in ("experience", "education", "skill", "certification", "language")
            for action in ("created", "updated", "deleted")
        ],
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "data_quality_before >= 0 AND data_quality_before <= 100",
            name=op.f("ck_candidate_enrichment_runs_quality_before_range"),
        ),
        sa.CheckConstraint(
            "data_quality_after IS NULL OR (data_quality_after >= 0 AND data_quality_after <= 100)",
            name=op.f("ck_candidate_enrichment_runs_quality_after_range"),
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name=op.f("ck_candidate_enrichment_runs_date_range_valid"),
        ),
        sa.CheckConstraint(
            " AND ".join(
                f"{action}_{section}_count >= 0"
                for section in ("experience", "education", "skill", "certification", "language")
                for action in ("created", "updated", "deleted")
            ),
            name=op.f("ck_candidate_enrichment_runs_counts_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            ondelete="CASCADE",
            name=op.f("fk_candidate_enrichment_runs_candidate_id_candidates"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_enrichment_runs")),
    )
    for column in ("candidate_id", "provider", "mode", "status", "created_at"):
        op.create_index(
            f"ix_candidate_enrichment_runs_{column}",
            "candidate_enrichment_runs",
            [column],
        )


def downgrade() -> None:
    for column in ("created_at", "status", "mode", "provider", "candidate_id"):
        op.drop_index(
            f"ix_candidate_enrichment_runs_{column}", table_name="candidate_enrichment_runs"
        )
    op.drop_table("candidate_enrichment_runs")
    op.drop_index("ix_candidate_certification_identity", table_name="candidate_certifications")
    op.drop_index("ix_candidate_education_identity", table_name="candidate_educations")
    op.drop_index("ix_candidate_experience_identity", table_name="candidate_experiences")
    with op.batch_alter_table("candidate_languages") as batch_op:
        batch_op.drop_column("source")
    with op.batch_alter_table("candidate_certifications") as batch_op:
        batch_op.drop_column("confidence")
        batch_op.drop_column("source")
        batch_op.drop_column("external_key")
    with op.batch_alter_table("candidate_educations") as batch_op:
        batch_op.drop_column("source")
        batch_op.drop_column("external_key")
    with op.batch_alter_table("candidate_experiences") as batch_op:
        batch_op.drop_column("source")
        batch_op.drop_column("external_key")
