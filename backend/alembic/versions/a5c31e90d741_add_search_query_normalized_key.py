"""add search query normalized key

Revision ID: a5c31e90d741
Revises: fcb788e29200
Create Date: 2026-07-13
"""

import re
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "a5c31e90d741"
down_revision: str | None = "fcb788e29200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WHITESPACE_RE = re.compile(r"\s+")


def _normalize(value: str) -> str:
    return WHITESPACE_RE.sub(" ", unicodedata.normalize("NFKC", value).casefold()).strip()


def _backfill_online() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, job_id, query_text FROM search_queries ORDER BY created_at ASC, id ASC")
    ).mappings()
    seen: set[tuple[str, str]] = set()
    for row in rows:
        base_key = _normalize(str(row["query_text"])) or f"query:{row['id']}"
        key = base_key[:1000]
        identity = (str(row["job_id"]), key)
        if identity in seen:
            suffix = f":{row['id']}"
            key = f"{base_key[: 1000 - len(suffix)]}{suffix}"
            identity = (str(row["job_id"]), key)
        seen.add(identity)
        connection.execute(
            sa.text("UPDATE search_queries SET normalized_query_key = :key WHERE id = :id"),
            {"key": key, "id": row["id"]},
        )


def upgrade() -> None:
    op.add_column(
        "search_queries",
        sa.Column("normalized_query_key", sa.String(length=1000), nullable=True),
    )
    if context.is_offline_mode():
        op.execute("UPDATE search_queries SET normalized_query_key = lower(trim(query_text))")
    else:
        _backfill_online()
    with op.batch_alter_table("search_queries") as batch_op:
        batch_op.alter_column(
            "normalized_query_key",
            existing_type=sa.String(length=1000),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_search_queries_job_normalized_key",
            ["job_id", "normalized_query_key"],
        )
    op.create_index(
        "ix_search_queries_normalized_query_key",
        "search_queries",
        ["normalized_query_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_search_queries_normalized_query_key", table_name="search_queries")
    with op.batch_alter_table("search_queries") as batch_op:
        batch_op.drop_constraint("uq_search_queries_job_normalized_key", type_="unique")
        batch_op.drop_column("normalized_query_key")
