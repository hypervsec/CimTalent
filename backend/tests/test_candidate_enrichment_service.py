from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import CandidateProfileStatus, CandidateSource
from app.db.models import Candidate, CandidateEnrichmentRun, CandidateExperience
from app.domain.enrichment.enums import EnrichmentImportMode, EnrichmentMode
from app.domain.enrichment.exceptions import CandidateEnrichmentPersistenceError
from app.repositories.candidate_enrichment import CandidateEnrichmentRepository
from app.repositories.enrichment_runs import EnrichmentRunRepository
from app.schemas.enrichment import CandidateEnrichmentImportRequest
from app.services.candidate_enrichment import CandidateEnrichmentService


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


def service() -> CandidateEnrichmentService:
    return CandidateEnrichmentService(CandidateEnrichmentRepository(), EnrichmentRunRepository())


async def candidate_id(session: AsyncSession) -> UUID:
    candidate = Candidate(source=CandidateSource.MANUAL, full_name="Demo")
    session.add(candidate)
    await session.commit()
    return candidate.id


def payload(**changes: object) -> CandidateEnrichmentImportRequest:
    values: dict[str, object] = {
        "mode": "fast",
        "identity": {
            "headline": {"value": "Backend Engineer", "source": "manual"},
            "current_title": {"value": "Engineer", "source": "manual"},
            "current_company": {"value": "Demo Co", "source": "manual"},
        },
        "experiences": [
            {
                "external_key": "exp-1",
                "position_title_raw": "Engineer",
                "company_name": "Demo Co",
                "start_date": "2020-01-01",
                "end_date": "2022-12-31",
            }
        ],
        "skills": [{"raw_name": "Python"}, {"raw_name": "MS SQL"}, {"raw_name": "REST API"}],
    }
    values.update(changes)
    return CandidateEnrichmentImportRequest.model_validate(values)


async def test_preview_is_read_only_and_import_is_idempotent(engine: AsyncEngine) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        identifier = await candidate_id(session)
        enrichment = service()
        preview = await enrichment.preview_import(session, identifier, payload())
        assert preview.experiences.create_count == 1
        assert preview.skills.create_count == 3
        assert await session.scalar(select(CandidateExperience.id)) is None

        first = await enrichment.import_enrichment(session, identifier, payload())
        assert first.candidate.profile_status is CandidateProfileStatus.PARTIAL
        assert first.candidate.total_experience_months == 36
        assert first.candidate.data_quality_score > first.quality_before
        assert first.run.created_experience_count == 1

        second = await enrichment.import_enrichment(session, identifier, payload())
        assert second.diff.experiences.create_count == 0
        assert second.diff.experiences.update_count == 1
        assert len(second.candidate.experiences) == 1
        assert len(second.candidate.skills) == 3


async def test_replace_all_and_identity_strategies(engine: AsyncEngine) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        identifier = await candidate_id(session)
        enrichment = service()
        await enrichment.import_enrichment(session, identifier, payload())
        replacement = payload(
            import_mode=EnrichmentImportMode.REPLACE_ALL,
            mode=EnrichmentMode.DEEP,
            identity_update_strategy="keep_existing",
            identity={"headline": {"value": "Must Not Replace", "source": "manual"}},
            experiences=[],
            skills=[],
        )
        outcome = await enrichment.import_enrichment(session, identifier, replacement)
        assert outcome.candidate.headline == "Backend Engineer"
        assert outcome.candidate.profile_status is CandidateProfileStatus.SCRAPED
        assert outcome.diff.experiences.delete_count == 1
        assert outcome.candidate.experiences == []
        assert outcome.candidate.skills == []


async def test_persistence_failure_rolls_back_profile_and_records_failed_run(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        identifier = await candidate_id(session)
        repository = CandidateEnrichmentRepository()
        enrichment = CandidateEnrichmentService(repository, EnrichmentRunRepository())

        async def fail_create(*args: object, **kwargs: object) -> None:
            raise SQLAlchemyError("forced persistence failure")

        monkeypatch.setattr(repository, "create", fail_create)
        with pytest.raises(CandidateEnrichmentPersistenceError):
            await enrichment.import_enrichment(session, identifier, payload())
        candidate = await session.get(Candidate, identifier)
        assert candidate is not None
        assert candidate.headline is None
        failed = list(await session.scalars(select(CandidateEnrichmentRun)))
        assert len(failed) == 1
        assert failed[0].status.value == "failed"


async def test_service_maps_repository_read_failures(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        identifier = await candidate_id(session)
        repository = CandidateEnrichmentRepository()
        runs = EnrichmentRunRepository()
        enrichment = CandidateEnrichmentService(repository, runs)

        async def fail(*args: object, **kwargs: object) -> None:
            raise SQLAlchemyError("forced read failure")

        monkeypatch.setattr(repository, "load_candidate_profile", fail)
        with pytest.raises(CandidateEnrichmentPersistenceError):
            await enrichment.get_profile(session, identifier)
        monkeypatch.undo()

        monkeypatch.setattr(runs, "get_by_id", fail)
        with pytest.raises(CandidateEnrichmentPersistenceError):
            await enrichment.get_run(session, identifier)
        monkeypatch.undo()

        now = datetime.now(UTC)
        await enrichment.import_enrichment(session, identifier, payload())
        items, total = await enrichment.list_candidate_runs(
            session,
            identifier,
            offset=0,
            limit=10,
            created_from=now - timedelta(minutes=1),
            created_to=now + timedelta(minutes=1),
        )
        assert total == 1
        assert len(items) == 1


async def test_repository_replace_section_and_flush(engine: AsyncEngine) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        identifier = await candidate_id(session)
        repository = CandidateEnrichmentRepository()
        rows = await repository.replace_section(
            session,
            model=CandidateExperience,
            candidate_id=identifier,
            rows=[
                {
                    "candidate_id": identifier,
                    "position_title_raw": "Engineer",
                    "skills_detected": [],
                }
            ],
        )
        await repository.flush(session)
        assert len(rows) == 1


async def test_current_position_is_derived_conservatively(engine: AsyncEngine) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        identifier = await candidate_id(session)
        enrichment = service()
        request = CandidateEnrichmentImportRequest.model_validate(
            {
                "experiences": [
                    {
                        "position_title_raw": "Older Role",
                        "company_name": "Old Co",
                        "start_date": "2020-01-01",
                        "is_current": True,
                        "sort_order": 0,
                    },
                    {
                        "position_title_raw": "Newest Role",
                        "company_name": "New Co",
                        "start_date": "2024-01-01",
                        "is_current": True,
                        "sort_order": 1,
                    },
                ]
            }
        )
        outcome = await enrichment.import_enrichment(session, identifier, request)
        assert outcome.candidate.current_title == "Newest Role"
        assert outcome.candidate.current_company == "New Co"
