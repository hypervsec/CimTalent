from io import StringIO
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.config import get_settings
from app.db import models as domain_models
from app.db.base import Base

REVISION = "fcb788e29200"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
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


def alembic_config(output_buffer: StringIO | None = None) -> Config:
    return Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=output_buffer)


def test_alembic_metadata_discovers_all_models() -> None:
    assert domain_models.Candidate.__tablename__ == "candidates"
    assert Base.metadata.tables.keys() == EXPECTED_TABLES


def test_initial_migration_file_exists() -> None:
    migration = (
        BACKEND_ROOT / "alembic" / "versions" / (f"{REVISION}_create_initial_domain_models.py")
    )
    assert migration.is_file()


def test_migration_upgrade_and_downgrade_sql_for_postgresql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/cimtalent",
    )
    get_settings.cache_clear()

    upgrade_output = StringIO()
    command.upgrade(alembic_config(upgrade_output), "head", sql=True)
    upgrade_sql = upgrade_output.getvalue()

    downgrade_output = StringIO()
    command.downgrade(alembic_config(downgrade_output), "head:base", sql=True)
    downgrade_sql = downgrade_output.getvalue()

    assert "CREATE TABLE job_postings" in upgrade_sql
    assert "CREATE TABLE candidates" in upgrade_sql
    assert "CREATE TABLE candidate_merge_audits" in upgrade_sql
    assert "CREATE TABLE candidate_enrichment_runs" in upgrade_sql
    assert "ix_candidates_profile_slug" in upgrade_sql
    assert "JSONB" in upgrade_sql
    assert "DROP TABLE job_postings" in downgrade_sql
    assert "DROP TABLE candidates" in downgrade_sql
    assert "DROP TABLE candidate_merge_audits" in downgrade_sql
    assert "DROP TABLE candidate_enrichment_runs" in downgrade_sql
    get_settings.cache_clear()


def test_migration_upgrade_and_downgrade_on_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "migration.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    config = alembic_config()

    command.upgrade(config, "head")
    sync_engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        upgraded_tables = set(inspect(sync_engine).get_table_names())
        assert EXPECTED_TABLES <= upgraded_tables
        assert "alembic_version" in upgraded_tables
        command.check(config)

        command.downgrade(config, "base")
        assert set(inspect(sync_engine).get_table_names()) == {"alembic_version"}
    finally:
        sync_engine.dispose()
        get_settings.cache_clear()


def test_normalized_query_migration_backfills_and_separates_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "query-key-migration.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    config = alembic_config()
    command.upgrade(config, REVISION)
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    insert_statement = text(
        "INSERT INTO search_queries "
        "(job_id, source, language, query_text, included_titles, included_skills, "
        "included_locations, status, result_count, id, created_at, updated_at) "
        "VALUES (:job_id, 'manual', 'en', :query_text, '[]', '[]', '[]', "
        "'ready', 0, :id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    try:
        with engine.begin() as connection:
            for suffix, query_text in (
                ("1", "  Python   Bursa "),
                ("2", "python bursa"),
            ):
                connection.execute(
                    insert_statement,
                    {
                        "job_id": "00000000-0000-0000-0000-000000000001",
                        "query_text": query_text,
                        "id": f"00000000-0000-0000-0000-00000000000{suffix}",
                    },
                )
        command.upgrade(config, "head")
        with engine.connect() as connection:
            keys = list(
                connection.execute(
                    text("SELECT normalized_query_key FROM search_queries ORDER BY id")
                ).scalars()
            )
        assert keys[0] == "python bursa"
        assert keys[1].startswith("python bursa:")
        assert len(set(keys)) == 2
    finally:
        engine.dispose()
        get_settings.cache_clear()
