from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import CandidateProfileStatus
from app.db.models import (
    Candidate,
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateLanguage,
    CandidateMatch,
    CandidateSkill,
    SearchResult,
    ShortlistEntry,
)
from app.domain.candidates import (
    CandidateFieldStrategy,
    CandidateListFilters,
    CandidateMergeConflictError,
    CandidateMergeError,
    CandidateNotFoundError,
    CandidatePersistenceError,
    CandidateSort,
    CandidateValidationError,
    CandidateWithCounts,
    DuplicateCandidateError,
    DuplicateCandidateSuggestion,
    InvalidCandidateStatusTransitionError,
    PagedCandidates,
)
from app.domain.candidates.merge import MERGE_FIELDS, duplicate_suggestion, select_merged_fields
from app.domain.candidates.normalizers import (
    clean_text,
    normalize_candidate_location,
    normalize_candidate_name,
    parse_headline_identity,
)
from app.domain.candidates.quality import (
    CandidateQualityInput,
    QualityBreakdown,
    calculate_candidate_quality,
)
from app.repositories.candidates import CandidateRepository
from app.sourcing.profile_url_normalizer import normalize_url

ALLOWED_STATUS_TRANSITIONS = {
    CandidateProfileStatus.DISCOVERED: {
        CandidateProfileStatus.QUEUED,
        CandidateProfileStatus.PARTIAL,
        CandidateProfileStatus.UNAVAILABLE,
        CandidateProfileStatus.FAILED,
    },
    CandidateProfileStatus.QUEUED: {
        CandidateProfileStatus.DISCOVERED,
        CandidateProfileStatus.SCRAPED,
        CandidateProfileStatus.PARTIAL,
        CandidateProfileStatus.UNAVAILABLE,
        CandidateProfileStatus.FAILED,
    },
    CandidateProfileStatus.SCRAPED: {
        CandidateProfileStatus.QUEUED,
        CandidateProfileStatus.PARTIAL,
        CandidateProfileStatus.UNAVAILABLE,
        CandidateProfileStatus.FAILED,
    },
    CandidateProfileStatus.PARTIAL: {
        CandidateProfileStatus.QUEUED,
        CandidateProfileStatus.SCRAPED,
        CandidateProfileStatus.UNAVAILABLE,
        CandidateProfileStatus.FAILED,
    },
    CandidateProfileStatus.UNAVAILABLE: {
        CandidateProfileStatus.QUEUED,
        CandidateProfileStatus.DISCOVERED,
    },
    CandidateProfileStatus.FAILED: {
        CandidateProfileStatus.QUEUED,
        CandidateProfileStatus.DISCOVERED,
    },
}

EXPLICIT_MERGE_FIELDS = frozenset(
    {
        "primary_profile_url",
        "full_name",
        "headline",
        "about",
        "discovery_title",
        "discovery_snippet",
        "location_raw",
        "city",
        "country",
        "current_title",
        "current_company",
        "total_experience_months",
        "open_to_work",
        "profile_status",
    }
)


@dataclass(frozen=True, slots=True)
class CandidateMergeOutcome:
    target_candidate_id: UUID
    source_candidate_ids: list[UUID]
    field_strategy: CandidateFieldStrategy
    dry_run: bool
    merged_fields: dict[str, object]
    conflicts: list[str]
    warnings: list[str]
    moved_counts: dict[str, int]
    candidate: CandidateWithCounts | None


class CandidateService:
    def __init__(self, repository: CandidateRepository) -> None:
        self.repository = repository

    async def create_candidate(
        self, session: AsyncSession, *, data: Mapping[str, object]
    ) -> CandidateWithCounts:
        prepared = self._prepare_data(data)
        self._validate_identity(prepared)
        normalized_url = prepared.get("normalized_profile_url")
        if isinstance(normalized_url, str):
            await self._reject_duplicate_url(session, normalized_url)
        prepared["data_quality_score"] = calculate_candidate_quality(
            self._quality_input(prepared)
        ).total_score
        try:
            candidate = await self.repository.create(session, data=prepared)
            await session.commit()
            record = await self.repository.get_by_id_with_counts(session, candidate.id)
        except IntegrityError as exc:
            await session.rollback()
            raise DuplicateCandidateError() from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            raise CandidatePersistenceError() from exc
        if record is None:
            raise CandidatePersistenceError("Created candidate could not be reloaded.")
        return record

    async def get_candidate(self, session: AsyncSession, candidate_id: UUID) -> CandidateWithCounts:
        try:
            record = await self.repository.get_by_id_with_counts(session, candidate_id)
        except SQLAlchemyError as exc:
            raise CandidatePersistenceError() from exc
        if record is None:
            raise CandidateNotFoundError(details={"candidate_id": str(candidate_id)})
        return record

    async def list_candidates(
        self,
        session: AsyncSession,
        *,
        page: int,
        page_size: int,
        filters: CandidateListFilters,
        sort: CandidateSort,
    ) -> PagedCandidates:
        try:
            items = await self.repository.list(
                session,
                offset=(page - 1) * page_size,
                limit=page_size,
                filters=filters,
                sort=sort,
            )
            total = await self.repository.count(session, filters=filters)
        except SQLAlchemyError as exc:
            raise CandidatePersistenceError() from exc
        return PagedCandidates(items, page, page_size, total)

    async def update_candidate(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        *,
        changes: Mapping[str, object],
    ) -> CandidateWithCounts:
        current = await self.get_candidate(session, candidate_id)
        candidate = current.candidate
        prepared = self._prepare_data(changes, partial=True)
        if "profile_status" in prepared:
            target = prepared["profile_status"]
            if not isinstance(target, CandidateProfileStatus):
                raise CandidateValidationError("profile_status is invalid.")
            self._validate_status_transition(candidate.profile_status, target)
        normalized_url = prepared.get("normalized_profile_url")
        if isinstance(normalized_url, str) and normalized_url != candidate.normalized_profile_url:
            await self._reject_duplicate_url(session, normalized_url, exclude_id=candidate.id)
        projected = {
            field_name: prepared.get(field_name, getattr(candidate, field_name))
            for field_name in (
                "primary_profile_url",
                "full_name",
                "discovery_title",
                "normalized_profile_url",
                "headline",
                "location_raw",
                "city",
                "country",
                "current_title",
                "current_company",
                "about",
                "discovery_snippet",
            )
        }
        self._validate_identity(projected)
        prepared["data_quality_score"] = calculate_candidate_quality(
            self._quality_input(projected, current)
        ).total_score
        try:
            await self.repository.update(session, candidate=candidate, changes=prepared)
            await session.commit()
            record = await self.repository.get_by_id_with_counts(session, candidate.id)
        except IntegrityError as exc:
            await session.rollback()
            raise DuplicateCandidateError() from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            raise CandidatePersistenceError() from exc
        if record is None:
            raise CandidatePersistenceError("Updated candidate could not be reloaded.")
        return record

    async def delete_candidate(self, session: AsyncSession, candidate_id: UUID) -> None:
        candidate = (await self.get_candidate(session, candidate_id)).candidate
        try:
            await self.repository.delete(session, candidate=candidate)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            raise CandidatePersistenceError() from exc

    async def list_candidate_search_results(
        self, session: AsyncSession, candidate_id: UUID
    ) -> list[SearchResult]:
        await self.get_candidate(session, candidate_id)
        try:
            return await self.repository.list_search_results(session, candidate_id)
        except SQLAlchemyError as exc:
            raise CandidatePersistenceError() from exc

    async def get_candidate_quality(
        self, session: AsyncSession, candidate_id: UUID
    ) -> QualityBreakdown:
        return calculate_candidate_quality(
            self._quality_input_from_record(await self.get_candidate(session, candidate_id))
        )

    async def find_duplicate_suggestions(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        *,
        min_score: float,
        limit: int,
    ) -> list[DuplicateCandidateSuggestion]:
        candidate = (await self.get_candidate(session, candidate_id)).candidate
        try:
            possible = await self.repository.find_duplicate_candidates(
                session, candidate, limit=max(limit * 5, 100)
            )
        except SQLAlchemyError as exc:
            raise CandidatePersistenceError() from exc
        base = self._duplicate_values(candidate)
        suggestions = [
            suggestion
            for other in possible
            if (
                suggestion := duplicate_suggestion(
                    candidate_id=other.id,
                    base=base,
                    other=self._duplicate_values(other),
                )
            )
            is not None
            and suggestion.score >= min_score
        ]
        return sorted(suggestions, key=lambda item: (-item.score, str(item.candidate_id)))[:limit]

    async def merge_candidates(
        self,
        session: AsyncSession,
        target_candidate_id: UUID,
        *,
        source_candidate_ids: list[UUID],
        field_strategy: CandidateFieldStrategy,
        explicit_field_values: Mapping[str, object] | None,
        dry_run: bool,
    ) -> CandidateMergeOutcome:
        self._validate_merge_ids(target_candidate_id, source_candidate_ids)
        explicit = self._prepare_explicit_merge_values(explicit_field_values)
        try:
            candidates = await self._load_merge_candidates(
                session, target_candidate_id, source_candidate_ids, lock=not dry_run
            )
            target = candidates[0]
            sources = candidates[1:]
            merged_fields, conflicts = select_merged_fields(
                self._candidate_values(target),
                [self._candidate_values(source) for source in sources],
                field_strategy,
                explicit,
            )
            self._validate_identity(merged_fields)
            source_counts = [
                await self.repository.get_by_id_with_counts(session, source.id)
                for source in sources
            ]
            if any(record is None for record in source_counts):
                raise CandidateMergeConflictError("A source candidate disappeared during merge.")
            moved_counts = self._preview_moved_counts(
                [record for record in source_counts if record is not None]
            )
            warnings = self._merge_warnings(conflicts)
            if dry_run:
                return CandidateMergeOutcome(
                    target_candidate_id,
                    source_candidate_ids,
                    field_strategy,
                    True,
                    merged_fields,
                    conflicts,
                    warnings,
                    moved_counts,
                    await self.repository.get_by_id_with_counts(session, target.id),
                )

            source_ids = [source.id for source in sources]
            moved_counts["search_results"] = await self.repository.move_search_results(
                session, source_ids=source_ids, target_id=target.id
            )
            moved_counts["experiences"] = await self.repository.move_children(
                session,
                model=CandidateExperience,
                source_ids=source_ids,
                target_id=target.id,
            )
            moved_counts["educations"] = await self.repository.move_children(
                session,
                model=CandidateEducation,
                source_ids=source_ids,
                target_id=target.id,
            )
            moved_counts["certifications"] = await self.repository.move_children(
                session,
                model=CandidateCertification,
                source_ids=source_ids,
                target_id=target.id,
            )
            skill_count, skill_warnings = await self._merge_skills(session, target.id, source_ids)
            language_count, language_warnings = await self._merge_languages(
                session, target.id, source_ids
            )
            match_warnings = await self._merge_matches(session, target.id, source_ids)
            shortlist_warnings = await self._merge_shortlist(session, target.id, source_ids)
            moved_counts["skills"] = skill_count
            moved_counts["languages"] = language_count
            warnings.extend(
                skill_warnings + language_warnings + match_warnings + shortlist_warnings
            )
            await self.repository.delete_candidates(session, source_ids)
            await self.repository.update(session, candidate=target, changes=merged_fields)
            record = await self.repository.get_by_id_with_counts(session, target.id)
            if record is None:
                raise CandidateMergeConflictError("Merge target disappeared during merge.")
            target.data_quality_score = calculate_candidate_quality(
                self._quality_input_from_record(record)
            ).total_score
            await session.flush()
            await self.repository.create_merge_audit(
                session,
                data={
                    "target_candidate_id": target.id,
                    "source_candidate_ids": [str(value) for value in source_ids],
                    "field_strategy": field_strategy.value,
                    "merged_fields": self._json_values(merged_fields),
                    "conflicts": conflicts,
                    "moved_search_result_count": moved_counts["search_results"],
                    "moved_experience_count": moved_counts["experiences"],
                    "moved_education_count": moved_counts["educations"],
                    "moved_skill_count": moved_counts["skills"],
                    "moved_certification_count": moved_counts["certifications"],
                    "moved_language_count": moved_counts["languages"],
                },
            )
            await session.commit()
            final_record = await self.repository.get_by_id_with_counts(session, target.id)
        except CandidateMergeConflictError:
            await session.rollback()
            raise
        except (IntegrityError, SQLAlchemyError) as exc:
            await session.rollback()
            raise CandidateMergeError("Candidate merge was rolled back.") from exc
        if final_record is None:
            raise CandidateMergeError("Merged candidate could not be reloaded.")
        return CandidateMergeOutcome(
            target_candidate_id,
            source_candidate_ids,
            field_strategy,
            False,
            merged_fields,
            conflicts,
            warnings,
            moved_counts,
            final_record,
        )

    async def _load_merge_candidates(
        self,
        session: AsyncSession,
        target_id: UUID,
        source_ids: list[UUID],
        *,
        lock: bool,
    ) -> list[Candidate]:
        identifiers = [target_id, *source_ids]
        records: dict[UUID, Candidate] = {}
        if lock:
            for candidate_id in sorted(identifiers, key=str):
                candidate = await self.repository.lock_by_id(session, candidate_id)
                if candidate is not None:
                    records[candidate.id] = candidate
        else:
            records = {
                candidate.id: candidate
                for candidate in await self.repository.list_by_ids(session, identifiers)
            }
        missing = [candidate_id for candidate_id in identifiers if candidate_id not in records]
        if missing:
            raise CandidateNotFoundError(
                "One or more merge candidates were not found.",
                details={"candidate_ids": [str(value) for value in missing]},
            )
        return [records[candidate_id] for candidate_id in identifiers]

    async def _merge_skills(
        self, session: AsyncSession, target_id: UUID, source_ids: list[UUID]
    ) -> tuple[int, list[str]]:
        records = await self.repository.list_skills_by_candidates(session, [target_id, *source_ids])
        target_by_key = {
            (record.normalized_name.casefold(), record.source): record
            for record in records
            if record.candidate_id == target_id
        }
        duplicates: list[CandidateSkill] = []
        source_records = [record for record in records if record.candidate_id in source_ids]
        for record in source_records:
            key = (record.normalized_name.casefold(), record.source)
            existing = target_by_key.get(key)
            if existing is None:
                record.candidate_id = target_id
                target_by_key[key] = record
            else:
                existing.confidence = max(existing.confidence, record.confidence)
                endorsements = [
                    value
                    for value in (existing.endorsement_count, record.endorsement_count)
                    if value is not None
                ]
                existing.endorsement_count = max(endorsements) if endorsements else None
                duplicates.append(record)
        if duplicates:
            await self.repository.delete_merge_records(session, duplicates)
        else:
            await session.flush()
        warnings = ["duplicate_skills_consolidated"] if duplicates else []
        return len(source_records), warnings

    async def _merge_languages(
        self, session: AsyncSession, target_id: UUID, source_ids: list[UUID]
    ) -> tuple[int, list[str]]:
        records = await self.repository.list_languages_by_candidates(
            session, [target_id, *source_ids]
        )
        target_by_key = {
            record.language_normalized.casefold(): record
            for record in records
            if record.candidate_id == target_id
        }
        duplicates: list[CandidateLanguage] = []
        source_records = [record for record in records if record.candidate_id in source_ids]
        for record in source_records:
            key = record.language_normalized.casefold()
            existing = target_by_key.get(key)
            if existing is None:
                record.candidate_id = target_id
                target_by_key[key] = record
            else:
                existing.confidence = max(existing.confidence, record.confidence)
                if not existing.proficiency and record.proficiency:
                    existing.proficiency = record.proficiency
                duplicates.append(record)
        if duplicates:
            await self.repository.delete_merge_records(session, duplicates)
        else:
            await session.flush()
        warnings = ["duplicate_languages_consolidated"] if duplicates else []
        return len(source_records), warnings

    async def _merge_matches(
        self, session: AsyncSession, target_id: UUID, source_ids: list[UUID]
    ) -> list[str]:
        records = await self.repository.list_matches_by_candidates(
            session, [target_id, *source_ids]
        )
        target_by_job = {
            record.job_id: record for record in records if record.candidate_id == target_id
        }
        duplicates: list[CandidateMatch] = []
        for record in records:
            if record.candidate_id not in source_ids:
                continue
            existing = target_by_job.get(record.job_id)
            if existing is None:
                record.candidate_id = target_id
                target_by_job[record.job_id] = record
            else:
                existing.explanation = self._join_notes(
                    existing.explanation, record.explanation, "Merged match explanation"
                )
                for field_name in (
                    "matched_requirements",
                    "missing_requirements",
                    "uncertain_requirements",
                ):
                    target_values = getattr(existing, field_name)
                    for value in getattr(record, field_name):
                        if value not in target_values:
                            target_values.append(value)
                duplicates.append(record)
        if duplicates:
            await self.repository.delete_merge_records(session, duplicates)
        else:
            await session.flush()
        return ["match_conflicts_consolidated_without_explanation_loss"] if duplicates else []

    async def _merge_shortlist(
        self, session: AsyncSession, target_id: UUID, source_ids: list[UUID]
    ) -> list[str]:
        records = await self.repository.list_shortlist_by_candidates(
            session, [target_id, *source_ids]
        )
        target_by_job = {
            record.job_id: record for record in records if record.candidate_id == target_id
        }
        duplicates: list[ShortlistEntry] = []
        for record in records:
            if record.candidate_id not in source_ids:
                continue
            existing = target_by_job.get(record.job_id)
            if existing is None:
                record.candidate_id = target_id
                target_by_job[record.job_id] = record
            else:
                existing.recruiter_note = self._join_notes(
                    existing.recruiter_note, record.recruiter_note, "Merged recruiter note"
                )
                duplicates.append(record)
        if duplicates:
            await self.repository.delete_merge_records(session, duplicates)
        else:
            await session.flush()
        return ["shortlist_conflicts_consolidated_without_note_loss"] if duplicates else []

    @staticmethod
    def _validate_merge_ids(target_id: UUID, source_ids: list[UUID]) -> None:
        if not source_ids:
            raise CandidateMergeConflictError("At least one source candidate is required.")
        if len(source_ids) > 20:
            raise CandidateMergeConflictError("At most 20 source candidates can be merged.")
        if len(set(source_ids)) != len(source_ids):
            raise CandidateMergeConflictError("Duplicate source candidate IDs are not allowed.")
        if target_id in source_ids:
            raise CandidateMergeConflictError("Target candidate cannot also be a source.")

    @classmethod
    def _prepare_explicit_merge_values(
        cls, values: Mapping[str, object] | None
    ) -> dict[str, object]:
        if not values:
            return {}
        unknown = set(values) - EXPLICIT_MERGE_FIELDS
        if unknown:
            raise CandidateMergeConflictError(
                "Explicit merge values contain protected fields.",
                details={"fields": sorted(unknown)},
            )
        prepared = dict(values)
        status = prepared.get("profile_status")
        if isinstance(status, str):
            try:
                prepared["profile_status"] = CandidateProfileStatus(status)
            except ValueError as exc:
                raise CandidateMergeConflictError("Explicit profile_status is invalid.") from exc
        months = prepared.get("total_experience_months")
        if months is not None and (
            not isinstance(months, int) or isinstance(months, bool) or months < 0
        ):
            raise CandidateMergeConflictError(
                "Explicit total_experience_months must be a non-negative integer."
            )
        return cls._prepare_data(prepared, partial=True)

    @staticmethod
    def _candidate_values(candidate: Candidate) -> dict[str, object]:
        values = {field_name: getattr(candidate, field_name) for field_name in MERGE_FIELDS}
        values["updated_at"] = candidate.updated_at
        return values

    @staticmethod
    def _preview_moved_counts(records: list[CandidateWithCounts]) -> dict[str, int]:
        return {
            "search_results": sum(record.search_result_count for record in records),
            "experiences": sum(record.experience_count for record in records),
            "educations": sum(record.education_count for record in records),
            "skills": sum(record.skill_count for record in records),
            "certifications": sum(record.certification_count for record in records),
            "languages": sum(record.language_count for record in records),
        }

    @staticmethod
    def _merge_warnings(conflicts: list[str]) -> list[str]:
        warnings = [f"field_conflict:{field_name}" for field_name in conflicts]
        if "normalized_profile_url" in conflicts:
            warnings.append("profile_url_conflict_requires_identity_review")
        return warnings

    @staticmethod
    def _json_values(values: Mapping[str, object]) -> dict[str, object]:
        output: dict[str, object] = {}
        for key, value in values.items():
            if isinstance(value, Enum):
                output[key] = value.value
            elif isinstance(value, datetime):
                output[key] = value.isoformat()
            elif isinstance(value, UUID):
                output[key] = str(value)
            else:
                output[key] = value
        return output

    @staticmethod
    def _join_notes(current: str | None, source: str | None, label: str) -> str | None:
        left = clean_text(current)
        right = clean_text(source)
        if right is None or right == left:
            return left
        if left is None:
            return right
        return f"{left}\n\n[{label}]\n{right}"

    async def _reject_duplicate_url(
        self, session: AsyncSession, normalized_url: str, *, exclude_id: UUID | None = None
    ) -> None:
        try:
            existing = await self.repository.get_by_normalized_profile_url(session, normalized_url)
        except SQLAlchemyError as exc:
            raise CandidatePersistenceError() from exc
        if existing is not None and existing.id != exclude_id:
            raise DuplicateCandidateError(details={"existing_candidate_id": str(existing.id)})

    @staticmethod
    def _prepare_data(data: Mapping[str, object], *, partial: bool = False) -> dict[str, object]:
        prepared = dict(data)
        if "primary_profile_url" in prepared:
            raw_url = prepared["primary_profile_url"]
            if raw_url is None:
                prepared["normalized_profile_url"] = None
                prepared["profile_slug"] = None
            elif isinstance(raw_url, str):
                normalized = normalize_url(raw_url)
                if normalized is None:
                    raise CandidateValidationError("primary_profile_url must be a valid HTTP URL.")
                if (
                    normalized.source_domain == "linkedin.com"
                    and not normalized.candidate_profile_slug
                ):
                    raise CandidateValidationError("LinkedIn URL must identify a person profile.")
                prepared["primary_profile_url"] = raw_url.strip()
                prepared["normalized_profile_url"] = normalized.value
                prepared["profile_slug"] = normalized.candidate_profile_slug
            else:
                raise CandidateValidationError("primary_profile_url must be a string or null.")
        if "full_name" in prepared:
            value = prepared["full_name"]
            prepared["full_name"] = normalize_candidate_name(
                value if isinstance(value, str) else None
            )
        if "headline" in prepared:
            value = prepared["headline"]
            headline = parse_headline_identity(value if isinstance(value, str) else None)
            prepared["headline"] = headline.cleaned_headline
            if headline.confidence >= 0.9:
                if not prepared.get("current_title"):
                    prepared["current_title"] = headline.current_title
                if not prepared.get("current_company"):
                    prepared["current_company"] = headline.current_company
        if "location_raw" in prepared:
            value = prepared["location_raw"]
            location = normalize_candidate_location(value if isinstance(value, str) else None)
            prepared["location_raw"] = location.location_raw
            if not prepared.get("city"):
                prepared["city"] = location.city
            if not prepared.get("country"):
                prepared["country"] = location.country
        for field_name in (
            "about",
            "discovery_title",
            "discovery_snippet",
            "city",
            "country",
            "current_title",
            "current_company",
        ):
            value = prepared.get(field_name)
            if isinstance(value, str):
                prepared[field_name] = clean_text(value)
        if not partial:
            prepared.setdefault("profile_status", CandidateProfileStatus.DISCOVERED)
        return prepared

    @staticmethod
    def _validate_identity(data: Mapping[str, object]) -> None:
        if not any(
            isinstance(data.get(field_name), str) and bool(str(data[field_name]).strip())
            for field_name in ("primary_profile_url", "full_name", "discovery_title")
        ):
            raise CandidateValidationError("At least one candidate identity field is required.")

    @staticmethod
    def _validate_status_transition(
        current: CandidateProfileStatus, target: CandidateProfileStatus
    ) -> None:
        if current is target:
            return
        if target not in ALLOWED_STATUS_TRANSITIONS[current]:
            raise InvalidCandidateStatusTransitionError(
                details={"from": current.value, "to": target.value}
            )

    @staticmethod
    def _quality_input(
        values: Mapping[str, object], counts: CandidateWithCounts | None = None
    ) -> CandidateQualityInput:
        def string(field_name: str) -> str | None:
            value = values.get(field_name)
            return value if isinstance(value, str) else None

        return CandidateQualityInput(
            full_name=string("full_name"),
            normalized_profile_url=string("normalized_profile_url"),
            headline=string("headline"),
            location_raw=string("location_raw"),
            city=string("city"),
            country=string("country"),
            current_title=string("current_title"),
            current_company=string("current_company"),
            about=string("about"),
            discovery_snippet=string("discovery_snippet"),
            experience_count=counts.experience_count if counts else 0,
            education_count=counts.education_count if counts else 0,
            skill_count=counts.skill_count if counts else 0,
        )

    @classmethod
    def _quality_input_from_record(cls, record: CandidateWithCounts) -> CandidateQualityInput:
        fields = (
            "full_name",
            "normalized_profile_url",
            "headline",
            "location_raw",
            "city",
            "country",
            "current_title",
            "current_company",
            "about",
            "discovery_snippet",
        )
        return cls._quality_input(
            {field_name: getattr(record.candidate, field_name) for field_name in fields}, record
        )

    @staticmethod
    def _duplicate_values(candidate: Candidate) -> dict[str, str | None]:
        return {
            "normalized_profile_url": candidate.normalized_profile_url,
            "profile_slug": candidate.profile_slug,
            "full_name": candidate.full_name,
            "headline": candidate.headline,
            "city": candidate.city,
            "current_company": candidate.current_company,
        }
