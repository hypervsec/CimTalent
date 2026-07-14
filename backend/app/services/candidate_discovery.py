from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import CandidateProfileStatus, CandidateSource, SearchSource
from app.db.models import Candidate, SearchResult
from app.domain.candidates import (
    CandidateDiscoveryAction,
    CandidateDiscoveryDecision,
    CandidateDiscoveryInput,
    CandidateDiscoverySummary,
    CandidateMatchedBy,
    CandidatePersistenceError,
    CandidateWithCounts,
    SearchResultNotEligibleError,
)
from app.domain.candidates.normalizers import (
    evaluate_candidate_eligibility,
    normalize_candidate_location,
    normalize_candidate_name,
    parse_headline_identity,
)
from app.domain.candidates.quality import CandidateQualityInput, calculate_candidate_quality
from app.domain.jobs import JobNotFoundError
from app.domain.sourcing import SearchResultNotFoundError
from app.repositories.candidates import CandidateRepository
from app.repositories.jobs import JobRepository
from app.repositories.search_results import SearchResultRepository
from app.schemas.candidates import DiscoverCandidatesRequest
from app.sourcing.profile_url_normalizer import NormalizedUrl, normalize_url


@dataclass(frozen=True, slots=True)
class SingleDiscoveryResult:
    decision: CandidateDiscoveryDecision
    candidate: CandidateWithCounts | None


class CandidateDiscoveryService:
    def __init__(
        self,
        candidate_repository: CandidateRepository,
        result_repository: SearchResultRepository,
        job_repository: JobRepository,
    ) -> None:
        self.candidates = candidate_repository
        self.results = result_repository
        self.jobs = job_repository

    async def discover_from_result(
        self, session: AsyncSession, result_id: UUID
    ) -> SingleDiscoveryResult:
        try:
            result = await self.results.get_by_id_with_query(session, result_id)
        except SQLAlchemyError as exc:
            raise CandidatePersistenceError() from exc
        if result is None:
            raise SearchResultNotFoundError(details={"result_id": str(result_id)})
        if result.candidate_id is not None:
            record = await self.candidates.get_by_id_with_counts(session, result.candidate_id)
            return SingleDiscoveryResult(
                CandidateDiscoveryDecision(
                    CandidateDiscoveryAction.LINKED_EXISTING,
                    result.candidate_id,
                    result.id,
                    "search_result_already_linked",
                    1.0,
                    CandidateMatchedBy.NORMALIZED_PROFILE_URL,
                    True,
                ),
                record,
            )
        normalized = normalize_url(result.source_url)
        data = self._discovery_input(result, normalized)
        eligibility = evaluate_candidate_eligibility(data)
        if not eligibility.eligible:
            raise SearchResultNotEligibleError(
                details={"search_result_id": str(result.id), "reason": eligibility.reason}
            )
        try:
            candidate, matched_by, created = await self._find_or_create(
                session, result=result, normalized=normalized, data=data
            )
            await self.results.assign_candidate(session, result=result, candidate_id=candidate.id)
            await session.commit()
            record = await self.candidates.get_by_id_with_counts(session, candidate.id)
        except IntegrityError as exc:
            await session.rollback()
            raise CandidatePersistenceError(
                "Candidate discovery conflicted with persisted data."
            ) from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            raise CandidatePersistenceError() from exc
        if record is None:
            raise CandidatePersistenceError("Discovered candidate could not be reloaded.")
        return SingleDiscoveryResult(
            CandidateDiscoveryDecision(
                CandidateDiscoveryAction.CREATED
                if created
                else CandidateDiscoveryAction.LINKED_EXISTING,
                candidate.id,
                result.id,
                "candidate_created" if created else "exact_candidate_identity_match",
                eligibility.confidence,
                matched_by,
            ),
            record,
        )

    async def discover_for_job(
        self,
        session: AsyncSession,
        job_id: UUID,
        request: DiscoverCandidatesRequest,
    ) -> CandidateDiscoverySummary:
        try:
            if not await self.jobs.exists(session, job_id):
                raise JobNotFoundError(details={"job_id": str(job_id)})
            results = await self.results.list_unassigned_by_job(
                session,
                job_id=job_id,
                limit=request.max_results,
                only_unassigned=request.only_unassigned,
            )
        except SQLAlchemyError as exc:
            raise CandidatePersistenceError() from exc
        if request.dry_run:
            return await self._dry_run(session, job_id, results, request)

        decisions: list[CandidateDiscoveryDecision] = []
        created_count = 0
        linked_count = 0
        eligible_count = 0
        try:
            for result in results:
                if result.candidate_id is not None:
                    decisions.append(self._already_linked_decision(result))
                    linked_count += 1
                    eligible_count += 1
                    continue
                normalized = normalize_url(result.source_url)
                data = self._discovery_input(result, normalized)
                eligibility = evaluate_candidate_eligibility(data)
                skip_reason = self._skip_reason(
                    result, eligibility.confidence, eligibility.eligible, request
                )
                if skip_reason:
                    decisions.append(
                        self._skip_decision(result.id, skip_reason, eligibility.confidence)
                    )
                    continue
                eligible_count += 1
                candidate, matched_by, created = await self._find_or_create(
                    session, result=result, normalized=normalized, data=data
                )
                await self.results.assign_candidate(
                    session, result=result, candidate_id=candidate.id
                )
                decisions.append(
                    CandidateDiscoveryDecision(
                        CandidateDiscoveryAction.CREATED
                        if created
                        else CandidateDiscoveryAction.LINKED_EXISTING,
                        candidate.id,
                        result.id,
                        "candidate_created" if created else "exact_candidate_identity_match",
                        eligibility.confidence,
                        matched_by,
                    )
                )
                created_count += int(created)
                linked_count += int(not created)
            await session.commit()
        except (IntegrityError, SQLAlchemyError) as exc:
            await session.rollback()
            raise CandidatePersistenceError("Bulk candidate discovery was rolled back.") from exc
        return self._summary(
            job_id,
            results,
            decisions,
            eligible_count,
            created_count,
            linked_count,
        )

    async def _dry_run(
        self,
        session: AsyncSession,
        job_id: UUID,
        results: list[SearchResult],
        request: DiscoverCandidatesRequest,
    ) -> CandidateDiscoverySummary:
        decisions: list[CandidateDiscoveryDecision] = []
        planned_urls: set[str] = set()
        created_count = linked_count = eligible_count = 0
        for result in results:
            if result.candidate_id is not None:
                decision = self._already_linked_decision(result, dry_run=True)
                decisions.append(decision)
                eligible_count += 1
                linked_count += 1
                continue
            normalized = normalize_url(result.source_url)
            data = self._discovery_input(result, normalized)
            eligibility = evaluate_candidate_eligibility(data)
            skip_reason = self._skip_reason(
                result, eligibility.confidence, eligibility.eligible, request
            )
            if skip_reason:
                decisions.append(
                    self._skip_decision(
                        result.id, skip_reason, eligibility.confidence, dry_run=True
                    )
                )
                continue
            eligible_count += 1
            existing, matched_by = await self._find_existing(session, normalized)
            would_link = existing is not None or data.normalized_url in planned_urls
            decisions.append(
                CandidateDiscoveryDecision(
                    CandidateDiscoveryAction.WOULD_LINK
                    if would_link
                    else CandidateDiscoveryAction.WOULD_CREATE,
                    existing.id if existing else None,
                    result.id,
                    "would_link_exact_identity" if would_link else "would_create_candidate",
                    eligibility.confidence,
                    matched_by if existing else CandidateMatchedBy.NONE,
                )
            )
            if would_link:
                linked_count += 1
            else:
                created_count += 1
                planned_urls.add(data.normalized_url)
        return self._summary(
            job_id,
            results,
            decisions,
            eligible_count,
            created_count,
            linked_count,
        )

    async def _find_or_create(
        self,
        session: AsyncSession,
        *,
        result: SearchResult,
        normalized: NormalizedUrl | None,
        data: CandidateDiscoveryInput,
    ) -> tuple[Candidate, CandidateMatchedBy, bool]:
        existing, matched_by = await self._find_existing(session, normalized)
        if existing is not None:
            return existing, matched_by, False
        candidate_data = self._build_candidate_data(result, normalized)
        candidate_data["data_quality_score"] = calculate_candidate_quality(
            CandidateQualityInput(
                full_name=candidate_data.get("full_name"),  # type: ignore[arg-type]
                normalized_profile_url=candidate_data.get("normalized_profile_url"),  # type: ignore[arg-type]
                headline=candidate_data.get("headline"),  # type: ignore[arg-type]
                location_raw=candidate_data.get("location_raw"),  # type: ignore[arg-type]
                city=candidate_data.get("city"),  # type: ignore[arg-type]
                country=candidate_data.get("country"),  # type: ignore[arg-type]
                current_title=candidate_data.get("current_title"),  # type: ignore[arg-type]
                current_company=candidate_data.get("current_company"),  # type: ignore[arg-type]
                discovery_snippet=candidate_data.get("discovery_snippet"),  # type: ignore[arg-type]
            )
        ).total_score
        return (
            await self.candidates.create(session, data=candidate_data),
            CandidateMatchedBy.NONE,
            True,
        )

    async def _find_existing(
        self, session: AsyncSession, normalized: NormalizedUrl | None
    ) -> tuple[Candidate | None, CandidateMatchedBy]:
        if normalized is None:
            return None, CandidateMatchedBy.NONE
        existing = await self.candidates.get_by_normalized_profile_url(session, normalized.value)
        if existing is not None:
            return existing, CandidateMatchedBy.NORMALIZED_PROFILE_URL
        if normalized.source_domain == "linkedin.com" and normalized.candidate_profile_slug:
            existing = await self.candidates.get_by_linkedin_slug(
                session, normalized.candidate_profile_slug
            )
            if existing is not None:
                return existing, CandidateMatchedBy.PROFILE_SLUG
        return None, CandidateMatchedBy.NONE

    @staticmethod
    def _build_candidate_data(
        result: SearchResult, normalized: NormalizedUrl | None
    ) -> dict[str, object]:
        name = normalize_candidate_name(result.displayed_name)
        headline = parse_headline_identity(result.displayed_headline)
        location = normalize_candidate_location(result.displayed_location)
        return {
            "source": CandidateDiscoveryService._candidate_source(result.search_query.source),
            "primary_profile_url": result.source_url,
            "normalized_profile_url": normalized.value if normalized else None,
            "profile_slug": normalized.candidate_profile_slug if normalized else None,
            "full_name": name,
            "headline": headline.cleaned_headline,
            "about": None,
            "discovery_title": result.title,
            "discovery_snippet": result.snippet,
            "location_raw": location.location_raw,
            "city": location.city,
            "country": location.country,
            "current_title": headline.current_title if headline.confidence >= 0.9 else None,
            "current_company": headline.current_company if headline.confidence >= 0.9 else None,
            "profile_status": CandidateProfileStatus.DISCOVERED,
            "last_scraped_at": None,
        }

    @staticmethod
    def _discovery_input(
        result: SearchResult, normalized: NormalizedUrl | None
    ) -> CandidateDiscoveryInput:
        return CandidateDiscoveryInput(
            search_result_id=result.id,
            normalized_url=normalized.value if normalized else result.normalized_url,
            source_url=result.source_url,
            source_domain=normalized.source_domain if normalized else result.source_domain,
            displayed_name=result.displayed_name,
            displayed_headline=result.displayed_headline,
            displayed_location=result.displayed_location,
            title=result.title,
            snippet=result.snippet,
            candidate_profile_slug=normalized.candidate_profile_slug if normalized else None,
        )

    @staticmethod
    def _candidate_source(source: SearchSource) -> CandidateSource:
        return {
            SearchSource.GOOGLE_XRAY: CandidateSource.GOOGLE_XRAY,
            SearchSource.PROFESSIONAL_NETWORK: CandidateSource.PROFESSIONAL_NETWORK,
            SearchSource.MANUAL: CandidateSource.IMPORTED,
        }[source]

    @staticmethod
    def _skip_reason(
        result: SearchResult,
        confidence: float,
        eligible: bool,
        request: DiscoverCandidatesRequest,
    ) -> str | None:
        domain = (result.source_domain or "").casefold()
        if request.include_domains and domain not in request.include_domains:
            return "domain_not_included"
        if domain in request.exclude_domains:
            return "domain_excluded"
        if not eligible:
            return "search_result_not_eligible"
        if confidence < request.minimum_eligibility_confidence:
            return "eligibility_confidence_below_minimum"
        return None

    @staticmethod
    def _skip_decision(
        result_id: UUID, reason: str, confidence: float, *, dry_run: bool = False
    ) -> CandidateDiscoveryDecision:
        return CandidateDiscoveryDecision(
            CandidateDiscoveryAction.WOULD_SKIP if dry_run else CandidateDiscoveryAction.SKIPPED,
            None,
            result_id,
            reason,
            confidence,
            CandidateMatchedBy.NONE,
        )

    @staticmethod
    def _already_linked_decision(
        result: SearchResult, *, dry_run: bool = False
    ) -> CandidateDiscoveryDecision:
        return CandidateDiscoveryDecision(
            CandidateDiscoveryAction.WOULD_LINK
            if dry_run
            else CandidateDiscoveryAction.LINKED_EXISTING,
            result.candidate_id,
            result.id,
            "search_result_already_linked",
            1.0,
            CandidateMatchedBy.NORMALIZED_PROFILE_URL,
            True,
        )

    @staticmethod
    def _summary(
        job_id: UUID,
        results: list[SearchResult],
        decisions: list[CandidateDiscoveryDecision],
        eligible_count: int,
        created_count: int,
        linked_count: int,
    ) -> CandidateDiscoverySummary:
        return CandidateDiscoverySummary(
            job_id=job_id,
            received_result_count=len(results),
            candidate_eligible_count=eligible_count,
            created_candidate_count=created_count,
            linked_existing_count=linked_count,
            skipped_count=sum(
                item.action
                in {CandidateDiscoveryAction.SKIPPED, CandidateDiscoveryAction.WOULD_SKIP}
                for item in decisions
            ),
            invalid_count=sum(
                item.action is CandidateDiscoveryAction.INVALID for item in decisions
            ),
            decisions=decisions,
            warnings=[],
        )
