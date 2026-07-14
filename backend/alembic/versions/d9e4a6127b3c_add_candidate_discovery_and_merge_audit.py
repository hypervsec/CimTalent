"""add candidate discovery metadata and merge audit

Revision ID: d9e4a6127b3c
Revises: a5c31e90d741
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d9e4a6127b3c"
down_revision: str | None = "a5c31e90d741"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("profile_slug", sa.String(length=255), nullable=True))
    op.add_column("candidates", sa.Column("discovery_title", sa.String(length=1000), nullable=True))
    op.add_column("candidates", sa.Column("discovery_snippet", sa.Text(), nullable=True))
    op.create_index("ix_candidates_profile_slug", "candidates", ["profile_slug"], unique=False)
    op.create_table(
        "candidate_merge_audits",
        sa.Column("target_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("source_candidate_ids", sa.JSON(), nullable=False),
        sa.Column("field_strategy", sa.String(length=50), nullable=False),
        sa.Column("merged_fields", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("moved_search_result_count", sa.Integer(), nullable=False),
        sa.Column("moved_experience_count", sa.Integer(), nullable=False),
        sa.Column("moved_education_count", sa.Integer(), nullable=False),
        sa.Column("moved_skill_count", sa.Integer(), nullable=False),
        sa.Column("moved_certification_count", sa.Integer(), nullable=False),
        sa.Column("moved_language_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "moved_search_result_count >= 0 AND moved_experience_count >= 0 "
            "AND moved_education_count >= 0 AND moved_skill_count >= 0 "
            "AND moved_certification_count >= 0 AND moved_language_count >= 0",
            name=op.f("ck_candidate_merge_audits_moved_counts_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["target_candidate_id"],
            ["candidates.id"],
            name=op.f("fk_candidate_merge_audits_target_candidate_id_candidates"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_merge_audits")),
    )
    op.create_index(
        "ix_candidate_merge_audits_target_candidate_id",
        "candidate_merge_audits",
        ["target_candidate_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_merge_audits_target_candidate_id", table_name="candidate_merge_audits"
    )
    op.drop_table("candidate_merge_audits")
    op.drop_index("ix_candidates_profile_slug", table_name="candidates")
    with op.batch_alter_table("candidates") as batch_op:
        batch_op.drop_column("discovery_snippet")
        batch_op.drop_column("discovery_title")
        batch_op.drop_column("profile_slug")
