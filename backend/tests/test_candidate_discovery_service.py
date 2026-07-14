from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import CandidateSource, SearchLanguage, SearchSource
from app.db.models import Candidate, SearchQuery, SearchResult
from app.domain.candidates import (
    CandidatePersistenceError,
    CandidateWithCounts,
    SearchResultNotEligibleError,
)
from app.domain.jobs import JobNotFoundError
from app.domain.sourcing import SearchResultNotFoundError
from app.repositories.candidates import CandidateRepository
from app.repositories.jobs import JobRepository
from app.repositories.search_results import SearchResultRepository
from app.schemas.candidates import DiscoverCandidatesRequest
from app.services.candidate_discovery import CandidateDiscoveryService


def result(url: str = "https://linkedin.com/in/unit-person") -> SearchResult:
    query = SearchQuery(
        id=uuid4(),
        job_id=uuid4(),
        source=SearchSource.GOOGLE_XRAY,
        language=SearchLanguage.EN,
        query_text="unit",
        normalized_query_key="unit",
    )
    record = SearchResult(
        id=uuid4(),
        search_query_id=query.id,
        source_url=url,
        normalized_url=url,
        source_domain="linkedin.com",
        displayed_name="Unit Person",
    )
    record.search_query = query
    return record


def service() -> tuple[
    CandidateDiscoveryService,
    Mock,
    Mock,
    Mock,
    AsyncMock,
]:
    candidates = Mock(spec=CandidateRepository)
    results = Mock(spec=SearchResultRepository)
    jobs = Mock(spec=JobRepository)
    session = AsyncMock(spec=AsyncSession)
    return (
        CandidateDiscoveryService(
            cast(CandidateRepository, candidates),
            cast(SearchResultRepository, results),
            cast(JobRepository, jobs),
        ),
        candidates,
        results,
        jobs,
        session,
    )


async def test_single_discovery_repository_failures_and_missing_result() -> None:
    subject, _, results, _, session = service()
    results.get_by_id_with_query.side_effect = SQLAlchemyError("read failed")
    with pytest.raises(CandidatePersistenceError):
        await subject.discover_from_result(cast(AsyncSession, session), uuid4())
    results.get_by_id_with_query.side_effect = None
    results.get_by_id_with_query.return_value = None
    with pytest.raises(SearchResultNotFoundError):
        await subject.discover_from_result(cast(AsyncSession, session), uuid4())


async def test_single_discovery_already_linked_branch() -> None:
    subject, candidates, results, _, session = service()
    record = result()
    candidate = Candidate(id=uuid4(), source=CandidateSource.MANUAL, full_name="Existing")
    record.candidate_id = candidate.id
    results.get_by_id_with_query.return_value = record
    candidates.get_by_id_with_counts.return_value = CandidateWithCounts(candidate)
    outcome = await subject.discover_from_result(cast(AsyncSession, session), record.id)
    assert outcome.decision.was_already_linked is True
    assert outcome.candidate is not None


async def test_single_discovery_integrity_and_reload_failures() -> None:
    subject, candidates, results, _, session = service()
    record = result()
    created = Candidate(id=uuid4(), source=CandidateSource.GOOGLE_XRAY, full_name="Unit Person")
    results.get_by_id_with_query.return_value = record
    candidates.get_by_normalized_profile_url.return_value = None
    candidates.get_by_linkedin_slug.return_value = None
    candidates.create.return_value = created
    results.assign_candidate.side_effect = IntegrityError("insert", {}, RuntimeError())
    with pytest.raises(CandidatePersistenceError):
        await subject.discover_from_result(cast(AsyncSession, session), record.id)
    session.rollback.assert_awaited()

    results.assign_candidate.side_effect = None
    candidates.get_by_id_with_counts.return_value = None
    with pytest.raises(CandidatePersistenceError, match="could not be reloaded"):
        await subject.discover_from_result(cast(AsyncSession, session), record.id)


async def test_single_discovery_success_and_ineligible() -> None:
    subject, candidates, results, _, session = service()
    record = result()
    created = Candidate(id=uuid4(), source=CandidateSource.GOOGLE_XRAY, full_name="Unit Person")
    results.get_by_id_with_query.return_value = record
    candidates.get_by_normalized_profile_url.return_value = None
    candidates.get_by_linkedin_slug.return_value = None
    candidates.create.return_value = created
    candidates.get_by_id_with_counts.return_value = CandidateWithCounts(created)
    outcome = await subject.discover_from_result(cast(AsyncSession, session), record.id)
    assert outcome.decision.action.value == "created"
    session.commit.assert_awaited()

    blocked = result("https://linkedin.com/company/unit")
    results.get_by_id_with_query.return_value = blocked
    with pytest.raises(SearchResultNotEligibleError):
        await subject.discover_from_result(cast(AsyncSession, session), blocked.id)


async def test_bulk_missing_job_and_repository_failure() -> None:
    subject, _, results, jobs, session = service()
    request = DiscoverCandidatesRequest()
    jobs.exists.return_value = False
    with pytest.raises(JobNotFoundError):
        await subject.discover_for_job(cast(AsyncSession, session), uuid4(), request)
    jobs.exists.side_effect = SQLAlchemyError("job read failed")
    with pytest.raises(CandidatePersistenceError):
        await subject.discover_for_job(cast(AsyncSession, session), uuid4(), request)
    results.list_unassigned_by_job.assert_not_awaited()


async def test_bulk_already_linked_and_hidden_decision_helpers() -> None:
    subject, _, results, jobs, session = service()
    record = result()
    record.candidate_id = uuid4()
    jobs.exists.return_value = True
    results.list_unassigned_by_job.return_value = [record]
    summary = await subject.discover_for_job(
        cast(AsyncSession, session),
        record.search_query.job_id,
        DiscoverCandidatesRequest(only_unassigned=False),
    )
    assert summary.candidate_eligible_count == 1
    assert summary.linked_existing_count == 1
    assert summary.decisions[0].was_already_linked is True


async def test_bulk_rolls_back_on_assignment_failure() -> None:
    subject, candidates, results, jobs, session = service()
    record = result()
    created = Candidate(id=uuid4(), source=CandidateSource.GOOGLE_XRAY, full_name="Unit Person")
    jobs.exists.return_value = True
    results.list_unassigned_by_job.return_value = [record]
    candidates.get_by_normalized_profile_url.return_value = None
    candidates.get_by_linkedin_slug.return_value = None
    candidates.create.return_value = created
    results.assign_candidate.side_effect = SQLAlchemyError("assignment failed")
    with pytest.raises(CandidatePersistenceError, match="rolled back"):
        await subject.discover_for_job(
            cast(AsyncSession, session), record.search_query.job_id, DiscoverCandidatesRequest()
        )
    session.rollback.assert_awaited()


async def test_bulk_dry_run_plans_create_then_link() -> None:
    subject, candidates, results, jobs, session = service()
    first = result()
    second = result()
    jobs.exists.return_value = True
    results.list_unassigned_by_job.return_value = [first, second]
    candidates.get_by_normalized_profile_url.return_value = None
    candidates.get_by_linkedin_slug.return_value = None
    summary = await subject.discover_for_job(
        cast(AsyncSession, session),
        first.search_query.job_id,
        DiscoverCandidatesRequest(dry_run=True),
    )
    assert summary.created_candidate_count == 1
    assert summary.linked_existing_count == 1
    assert [item.action.value for item in summary.decisions] == ["would_create", "would_link"]


async def test_bulk_execute_success_with_skip() -> None:
    subject, candidates, results, jobs, session = service()
    eligible = result()
    blocked = result("https://linkedin.com/jobs/view/1")
    created = Candidate(id=uuid4(), source=CandidateSource.GOOGLE_XRAY, full_name="Unit Person")
    jobs.exists.return_value = True
    results.list_unassigned_by_job.return_value = [eligible, blocked]
    candidates.get_by_normalized_profile_url.return_value = None
    candidates.get_by_linkedin_slug.return_value = None
    candidates.create.return_value = created
    summary = await subject.discover_for_job(
        cast(AsyncSession, session), eligible.search_query.job_id, DiscoverCandidatesRequest()
    )
    assert summary.created_candidate_count == 1
    assert summary.skipped_count == 1
    session.commit.assert_awaited()
