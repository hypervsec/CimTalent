from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import CandidateProfileStatus, CandidateSource
from app.db.models import Candidate
from app.domain.candidates import (
    CandidateListFilters,
    CandidateNotFoundError,
    CandidatePersistenceError,
    CandidateSort,
    CandidateValidationError,
    CandidateWithCounts,
    DuplicateCandidateError,
)
from app.repositories.candidates import CandidateRepository
from app.services.candidates import CandidateService


def setup() -> tuple[CandidateService, Mock, AsyncMock, CandidateWithCounts]:
    repository = Mock(spec=CandidateRepository)
    session = AsyncMock(spec=AsyncSession)
    candidate = Candidate(
        id=uuid4(),
        source=CandidateSource.MANUAL,
        full_name="Service Candidate",
        headline="Backend Engineer",
        city="Bursa",
        profile_status=CandidateProfileStatus.DISCOVERED,
        data_quality_score=35,
    )
    record = CandidateWithCounts(candidate)
    return (
        CandidateService(cast(CandidateRepository, repository)),
        repository,
        session,
        record,
    )


async def test_candidate_service_direct_crud_list_quality_and_suggestions() -> None:
    service, repository, session, record = setup()
    repository.create.return_value = record.candidate
    repository.get_by_id_with_counts.return_value = record
    created = await service.create_candidate(
        cast(AsyncSession, session), data={"full_name": "Service Candidate"}
    )
    assert created is record

    repository.list.return_value = [record]
    repository.count.return_value = 1
    page = await service.list_candidates(
        cast(AsyncSession, session),
        page=1,
        page_size=20,
        filters=CandidateListFilters(),
        sort=CandidateSort(),
    )
    assert page.total_items == 1

    updated = await service.update_candidate(
        cast(AsyncSession, session), record.candidate.id, changes={"about": " Updated "}
    )
    assert updated is record
    repository.update.assert_awaited()

    quality = await service.get_candidate_quality(cast(AsyncSession, session), record.candidate.id)
    assert quality.total_score >= 0
    repository.list_search_results.return_value = []
    assert (
        await service.list_candidate_search_results(
            cast(AsyncSession, session), record.candidate.id
        )
        == []
    )

    other = Candidate(
        id=uuid4(),
        source=CandidateSource.IMPORTED,
        full_name="Service Candidate",
        headline="Backend Engineer",
        city="Bursa",
    )
    repository.find_duplicate_candidates.return_value = [other]
    suggestions = await service.find_duplicate_suggestions(
        cast(AsyncSession, session), record.candidate.id, min_score=0.8, limit=20
    )
    assert suggestions[0].score == 0.95

    await service.delete_candidate(cast(AsyncSession, session), record.candidate.id)
    repository.delete.assert_awaited()
    session.commit.assert_awaited()


async def test_candidate_service_maps_create_and_read_failures() -> None:
    service, repository, session, record = setup()
    repository.create.side_effect = IntegrityError("insert", {}, RuntimeError())
    with pytest.raises(DuplicateCandidateError):
        await service.create_candidate(
            cast(AsyncSession, session), data={"full_name": "Service Candidate"}
        )
    session.rollback.assert_awaited()

    repository.create.side_effect = SQLAlchemyError("write failed")
    with pytest.raises(CandidatePersistenceError):
        await service.create_candidate(
            cast(AsyncSession, session), data={"full_name": "Service Candidate"}
        )

    repository.create.side_effect = None
    repository.create.return_value = record.candidate
    repository.get_by_id_with_counts.return_value = None
    with pytest.raises(CandidatePersistenceError, match="could not be reloaded"):
        await service.create_candidate(
            cast(AsyncSession, session), data={"full_name": "Service Candidate"}
        )

    repository.get_by_id_with_counts.side_effect = SQLAlchemyError("read failed")
    with pytest.raises(CandidatePersistenceError):
        await service.get_candidate(cast(AsyncSession, session), record.candidate.id)


async def test_candidate_service_maps_list_and_relation_failures() -> None:
    service, repository, session, record = setup()
    repository.list.side_effect = SQLAlchemyError("list failed")
    with pytest.raises(CandidatePersistenceError):
        await service.list_candidates(
            cast(AsyncSession, session),
            page=1,
            page_size=20,
            filters=CandidateListFilters(),
            sort=CandidateSort(),
        )

    repository.list.side_effect = None
    repository.get_by_id_with_counts.return_value = record
    repository.list_search_results.side_effect = SQLAlchemyError("relation failed")
    with pytest.raises(CandidatePersistenceError):
        await service.list_candidate_search_results(
            cast(AsyncSession, session), record.candidate.id
        )

    repository.find_duplicate_candidates.side_effect = SQLAlchemyError("duplicate failed")
    with pytest.raises(CandidatePersistenceError):
        await service.find_duplicate_suggestions(
            cast(AsyncSession, session), record.candidate.id, min_score=0.8, limit=20
        )

    repository.delete.side_effect = SQLAlchemyError("delete failed")
    with pytest.raises(CandidatePersistenceError):
        await service.delete_candidate(cast(AsyncSession, session), record.candidate.id)


async def test_candidate_service_missing_invalid_update_and_duplicate_lookup() -> None:
    service, repository, session, record = setup()
    repository.get_by_id_with_counts.return_value = None
    with pytest.raises(CandidateNotFoundError):
        await service.get_candidate(cast(AsyncSession, session), record.candidate.id)

    repository.get_by_id_with_counts.return_value = record
    with pytest.raises(CandidateValidationError):
        await service.update_candidate(
            cast(AsyncSession, session),
            record.candidate.id,
            changes={"profile_status": "queued"},
        )

    repository.get_by_normalized_profile_url.side_effect = SQLAlchemyError("lookup failed")
    with pytest.raises(CandidatePersistenceError):
        await service._reject_duplicate_url(
            cast(AsyncSession, session), "https://example.com/person"
        )
    repository.get_by_normalized_profile_url.side_effect = None
    repository.get_by_normalized_profile_url.return_value = record.candidate
    with pytest.raises(DuplicateCandidateError):
        await service._reject_duplicate_url(
            cast(AsyncSession, session), "https://example.com/person"
        )


def test_candidate_service_preserves_explicit_headline_and_location_fields() -> None:
    prepared = CandidateService._prepare_data(
        {
            "headline": "Engineer at Inferred Company",
            "current_title": "Explicit Title",
            "current_company": "Explicit Company",
            "location_raw": "Bursa, Türkiye",
            "city": "Explicit City",
            "country": "Explicit Country",
        },
        partial=True,
    )
    assert prepared["current_title"] == "Explicit Title"
    assert prepared["current_company"] == "Explicit Company"
    assert prepared["city"] == "Explicit City"
    assert prepared["country"] == "Explicit Country"
