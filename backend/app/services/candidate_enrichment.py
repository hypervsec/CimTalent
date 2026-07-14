from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import TypeVar, cast
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import CandidateProfileStatus
from app.db.models import (
    Candidate,
    CandidateCertification,
    CandidateEducation,
    CandidateEnrichmentRun,
    CandidateExperience,
    CandidateLanguage,
    CandidateSkill,
)
from app.domain.candidates import CandidateNotFoundError
from app.domain.candidates.quality import (
    CandidateQualityInput,
    QualityBreakdown,
    calculate_candidate_quality,
)
from app.domain.enrichment.diff import (
    CandidateEnrichmentDiff,
    CollectionDiff,
    IdentityChange,
)
from app.domain.enrichment.enums import (
    CandidateEnrichmentStatus,
    EnrichmentImportMode,
    EnrichmentMode,
    EnrichmentProvider,
    IdentityUpdateStrategy,
)
from app.domain.enrichment.exceptions import (
    CandidateEnrichmentPersistenceError,
    EnrichmentRunNotFoundError,
    UnsupportedEnrichmentProviderError,
)
from app.domain.enrichment.normalizers import (
    experience_fingerprint,
    normalize_certification,
    normalize_education,
    normalize_experience,
    normalize_language,
    normalize_skill,
    total_experience_months,
)
from app.domain.enrichment.types import (
    EnrichedCertification,
    EnrichedEducation,
    EnrichedExperience,
    EnrichedLanguage,
    EnrichedSkill,
)
from app.domain.enrichment.validators import validate_evidence
from app.repositories.candidate_enrichment import CandidateEnrichmentRepository
from app.repositories.enrichment_runs import EnrichmentRunRepository
from app.schemas.enrichment import CandidateEnrichmentImportRequest

ModelChild = (
    CandidateExperience
    | CandidateEducation
    | CandidateSkill
    | CandidateCertification
    | CandidateLanguage
)
DomainChild = (
    EnrichedExperience
    | EnrichedEducation
    | EnrichedSkill
    | EnrichedCertification
    | EnrichedLanguage
)
TModel = TypeVar(
    "TModel",
    CandidateExperience,
    CandidateEducation,
    CandidateSkill,
    CandidateCertification,
    CandidateLanguage,
)
TDomain = TypeVar(
    "TDomain",
    EnrichedExperience,
    EnrichedEducation,
    EnrichedSkill,
    EnrichedCertification,
    EnrichedLanguage,
)


@dataclass(frozen=True, slots=True)
class PreparedEnrichment:
    identity: dict[str, tuple[object, float]]
    experiences: list[EnrichedExperience]
    educations: list[EnrichedEducation]
    skills: list[EnrichedSkill]
    certifications: list[EnrichedCertification]
    languages: list[EnrichedLanguage]
    sections: frozenset[str]


@dataclass(frozen=True, slots=True)
class EnrichmentOutcome:
    candidate: Candidate
    run: CandidateEnrichmentRun
    diff: CandidateEnrichmentDiff
    profile_status_before: CandidateProfileStatus
    quality_before: float


class CandidateEnrichmentService:
    def __init__(
        self,
        repository: CandidateEnrichmentRepository,
        run_repository: EnrichmentRunRepository,
    ) -> None:
        self.repository = repository
        self.run_repository = run_repository

    async def preview_import(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        payload: CandidateEnrichmentImportRequest,
    ) -> CandidateEnrichmentDiff:
        self._validate_provider(payload.provider)
        candidate = await self._load_candidate(session, candidate_id)
        prepared = self.build_result(payload)
        return self.calculate_diff(candidate, prepared, payload)

    async def import_enrichment(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        payload: CandidateEnrichmentImportRequest,
        *,
        allow_linkedin: bool = False,
    ) -> EnrichmentOutcome:
        self._validate_provider(payload.provider, allow_linkedin=allow_linkedin)
        candidate = await self._load_candidate(session, candidate_id)
        prepared = self.build_result(payload)
        diff = self.calculate_diff(candidate, prepared, payload)
        projected_experiences = self._project_experiences(
            candidate.experiences, prepared.experiences, payload
        )
        quality_before = candidate.data_quality_score
        status_before = candidate.profile_status
        now = datetime.now(UTC)
        run: CandidateEnrichmentRun | None = None
        try:
            run = await self.run_repository.create(
                session,
                data=self._run_start_data(candidate, prepared, payload, now),
            )
            self.apply_identity_changes(candidate, diff)
            await self.merge_experiences(
                session, candidate, prepared.experiences, payload, diff.experiences
            )
            await self.merge_educations(
                session, candidate, prepared.educations, payload, diff.educations
            )
            await self.merge_skills(session, candidate, prepared.skills, payload, diff.skills)
            await self.merge_certifications(
                session, candidate, prepared.certifications, payload, diff.certifications
            )
            await self.merge_languages(
                session, candidate, prepared.languages, payload, diff.languages
            )
            candidate.total_experience_months = total_experience_months(
                projected_experiences,
                today=now.date(),
            )
            candidate.profile_status = self._profile_status(payload)
            candidate.data_quality_score = self._quality(candidate, diff).total_score
            if payload.mode is EnrichmentMode.DEEP and not payload.is_partial:
                candidate.last_scraped_at = now
            await self.repository.flush(session)
            final_status = (
                CandidateEnrichmentStatus.PARTIAL
                if payload.is_partial
                else CandidateEnrichmentStatus.COMPLETED
            )
            await self.run_repository.update_status(
                session,
                run,
                final_status,
                changes=self._run_complete_data(run, diff, candidate, prepared, payload, now),
            )
            await session.commit()
            refreshed = await self._load_candidate(session, candidate_id)
            refreshed_run = await self.run_repository.get_by_id(session, run.id)
            if refreshed_run is None:
                raise CandidateEnrichmentPersistenceError("Completed run could not be reloaded.")
            return EnrichmentOutcome(refreshed, refreshed_run, diff, status_before, quality_before)
        except SQLAlchemyError as exc:
            await session.rollback()
            await self._record_failed_run(session, candidate_id, payload, quality_before, now)
            raise CandidateEnrichmentPersistenceError(
                "Candidate enrichment could not be persisted."
            ) from exc

    async def get_run(self, session: AsyncSession, run_id: UUID) -> CandidateEnrichmentRun:
        try:
            run = await self.run_repository.get_by_id(session, run_id)
        except SQLAlchemyError as exc:
            raise CandidateEnrichmentPersistenceError(
                "Enrichment run could not be loaded."
            ) from exc
        if run is None:
            raise EnrichmentRunNotFoundError(
                "Enrichment run was not found.", details={"run_id": str(run_id)}
            )
        return run

    async def list_candidate_runs(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        *,
        offset: int,
        limit: int,
        provider: EnrichmentProvider | None = None,
        mode: EnrichmentMode | None = None,
        status: CandidateEnrichmentStatus | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        sort_by: str = "created_at",
        descending: bool = True,
    ) -> tuple[list[CandidateEnrichmentRun], int]:
        await self._load_candidate(session, candidate_id)
        try:
            items = await self.run_repository.list_by_candidate(
                session,
                candidate_id,
                offset=offset,
                limit=limit,
                provider=provider,
                mode=mode,
                status=status,
                created_from=created_from,
                created_to=created_to,
                sort_by=sort_by,
                descending=descending,
            )
            total = await self.run_repository.count_by_candidate(
                session,
                candidate_id,
                provider=provider,
                mode=mode,
                status=status,
                created_from=created_from,
                created_to=created_to,
            )
        except SQLAlchemyError as exc:
            raise CandidateEnrichmentPersistenceError(
                "Enrichment runs could not be listed."
            ) from exc
        return items, total

    async def get_profile(self, session: AsyncSession, candidate_id: UUID) -> Candidate:
        return await self._load_candidate(session, candidate_id)

    def build_result(self, payload: CandidateEnrichmentImportRequest) -> PreparedEnrichment:
        identity: dict[str, tuple[object, float]] = {}
        if payload.identity:
            for field_name in (
                "full_name",
                "headline",
                "about",
                "location_raw",
                "city",
                "country",
                "current_title",
                "current_company",
                "open_to_work",
            ):
                extracted = getattr(payload.identity, field_name)
                if extracted is not None:
                    validate_evidence(extracted.evidence)
                    value = (
                        extracted.value.strip()
                        if isinstance(extracted.value, str)
                        else extracted.value
                    )
                    identity[field_name] = (value, extracted.confidence)
        experiences = self._deduplicate(
            [
                normalize_experience(EnrichedExperience(**item.model_dump(mode="python")))
                for item in payload.experiences
            ],
            self._experience_key,
        )
        if payload.identity_update_strategy is not IdentityUpdateStrategy.KEEP_EXISTING:
            current = self._select_current_experience(experiences)
            if current is not None:
                identity.setdefault(
                    "current_title", (current.position_title_raw, current.confidence)
                )
                if current.company_name:
                    identity.setdefault(
                        "current_company", (current.company_name, current.confidence)
                    )
        educations = self._deduplicate(
            [
                normalize_education(EnrichedEducation(**item.model_dump(mode="python")))
                for item in payload.educations
            ],
            self._education_key,
        )
        skills = self._deduplicate(
            [
                normalize_skill(EnrichedSkill(normalized_name="", **item.model_dump(mode="python")))
                for item in payload.skills
            ],
            lambda item: f"{item.normalized_name}|{item.source.value}",
        )
        certifications = self._deduplicate(
            [
                normalize_certification(EnrichedCertification(**item.model_dump(mode="python")))
                for item in payload.certifications
            ],
            self._certification_key,
        )
        languages = self._deduplicate(
            [
                normalize_language(
                    EnrichedLanguage(language_normalized="", **item.model_dump(mode="python"))
                )
                for item in payload.languages
            ],
            lambda item: item.language_normalized,
        )
        present = set(payload.model_fields_set) & {
            "identity",
            "experiences",
            "educations",
            "skills",
            "certifications",
            "languages",
        }
        return PreparedEnrichment(
            identity, experiences, educations, skills, certifications, languages, frozenset(present)
        )

    def calculate_diff(
        self,
        candidate: Candidate,
        prepared: PreparedEnrichment,
        payload: CandidateEnrichmentImportRequest,
    ) -> CandidateEnrichmentDiff:
        identity_changes = self._identity_diff(
            candidate, prepared.identity, payload.identity_update_strategy
        )
        experiences = self._collection_diff(
            "experiences",
            candidate.experiences,
            prepared.experiences,
            self._experience_model_key,
            self._experience_key,
            prepared.sections,
            payload.import_mode,
        )
        educations = self._collection_diff(
            "educations",
            candidate.educations,
            prepared.educations,
            self._education_model_key,
            self._education_key,
            prepared.sections,
            payload.import_mode,
        )
        skills = self._collection_diff(
            "skills",
            candidate.skills,
            prepared.skills,
            lambda item: f"{item.normalized_name}|{item.source.value}",
            lambda item: f"{item.normalized_name}|{item.source.value}",
            prepared.sections,
            payload.import_mode,
        )
        certifications = self._collection_diff(
            "certifications",
            candidate.certifications,
            prepared.certifications,
            self._certification_model_key,
            self._certification_key,
            prepared.sections,
            payload.import_mode,
        )
        languages = self._collection_diff(
            "languages",
            candidate.languages,
            prepared.languages,
            lambda item: item.language_normalized,
            lambda item: item.language_normalized,
            prepared.sections,
            payload.import_mode,
        )
        before = candidate.data_quality_score
        projected = self._projected_quality(
            candidate, identity_changes, experiences, educations, skills
        )
        return CandidateEnrichmentDiff(
            tuple(identity_changes),
            experiences,
            educations,
            skills,
            certifications,
            languages,
            before,
            projected,
            tuple(payload.warnings),
        )

    def apply_identity_changes(self, candidate: Candidate, diff: CandidateEnrichmentDiff) -> None:
        for change in diff.identity_changes:
            if change.action == "update":
                setattr(candidate, change.field, change.new_value)

    async def merge_experiences(
        self,
        session: AsyncSession,
        candidate: Candidate,
        items: list[EnrichedExperience],
        payload: CandidateEnrichmentImportRequest,
        diff: CollectionDiff,
    ) -> None:
        await self._merge_collection(
            session,
            candidate.id,
            candidate.experiences,
            items,
            self._experience_model_key,
            self._experience_key,
            CandidateExperience,
            self._experience_values,
            payload,
            "experiences",
        )

    async def merge_educations(
        self,
        session: AsyncSession,
        candidate: Candidate,
        items: list[EnrichedEducation],
        payload: CandidateEnrichmentImportRequest,
        diff: CollectionDiff,
    ) -> None:
        await self._merge_collection(
            session,
            candidate.id,
            candidate.educations,
            items,
            self._education_model_key,
            self._education_key,
            CandidateEducation,
            self._education_values,
            payload,
            "educations",
        )

    async def merge_skills(
        self,
        session: AsyncSession,
        candidate: Candidate,
        items: list[EnrichedSkill],
        payload: CandidateEnrichmentImportRequest,
        diff: CollectionDiff,
    ) -> None:
        await self._merge_collection(
            session,
            candidate.id,
            candidate.skills,
            items,
            self._skill_key,
            self._skill_key,
            CandidateSkill,
            self._skill_values,
            payload,
            "skills",
        )

    async def merge_certifications(
        self,
        session: AsyncSession,
        candidate: Candidate,
        items: list[EnrichedCertification],
        payload: CandidateEnrichmentImportRequest,
        diff: CollectionDiff,
    ) -> None:
        await self._merge_collection(
            session,
            candidate.id,
            candidate.certifications,
            items,
            self._certification_model_key,
            self._certification_key,
            CandidateCertification,
            self._certification_values,
            payload,
            "certifications",
        )

    async def merge_languages(
        self,
        session: AsyncSession,
        candidate: Candidate,
        items: list[EnrichedLanguage],
        payload: CandidateEnrichmentImportRequest,
        diff: CollectionDiff,
    ) -> None:
        await self._merge_collection(
            session,
            candidate.id,
            candidate.languages,
            items,
            self._language_key,
            self._language_key,
            CandidateLanguage,
            self._language_values,
            payload,
            "languages",
        )

    async def _merge_collection(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        existing: list[TModel],
        incoming: list[TDomain],
        model_key: Callable[[TModel], str],
        domain_key: Callable[[TDomain], str],
        model: type[TModel],
        values: Callable[[TDomain], dict[str, object]],
        payload: CandidateEnrichmentImportRequest,
        section: str,
    ) -> None:
        indexed = {model_key(item): item for item in existing}
        incoming_keys: set[str] = set()
        for item in incoming:
            key = domain_key(item)
            incoming_keys.add(key)
            row = {"candidate_id": candidate_id, **values(item)}
            matched = indexed.get(key)
            if matched is None:
                await self.repository.create(session, model, row)
            else:
                await self.repository.update(session, matched, values(item))
        should_delete = payload.import_mode is EnrichmentImportMode.REPLACE_ALL or (
            payload.import_mode is EnrichmentImportMode.REPLACE_SECTIONS
            and section in payload.model_fields_set
        )
        if should_delete:
            await self.repository.delete_records(
                session, [item for item in existing if model_key(item) not in incoming_keys]
            )

    async def _load_candidate(self, session: AsyncSession, candidate_id: UUID) -> Candidate:
        try:
            candidate = await self.repository.load_candidate_profile(session, candidate_id)
        except SQLAlchemyError as exc:
            raise CandidateEnrichmentPersistenceError(
                "Candidate profile could not be loaded."
            ) from exc
        if candidate is None:
            raise CandidateNotFoundError(details={"candidate_id": str(candidate_id)})
        return candidate

    @staticmethod
    def _validate_provider(provider: EnrichmentProvider, *, allow_linkedin: bool = False) -> None:
        allowed = {EnrichmentProvider.MANUAL}
        if allow_linkedin:
            allowed.add(EnrichmentProvider.LINKEDIN)
        if provider not in allowed:
            raise UnsupportedEnrichmentProviderError("Only the manual provider is implemented.")

    @staticmethod
    def _deduplicate(items: list[TDomain], key: Callable[[TDomain], str]) -> list[TDomain]:
        result: dict[str, TDomain] = {}
        for item in items:
            result[key(item)] = item
        return list(result.values())

    @staticmethod
    def _identity_diff(
        candidate: Candidate,
        incoming: Mapping[str, tuple[object, float]],
        strategy: IdentityUpdateStrategy,
    ) -> list[IdentityChange]:
        changes: list[IdentityChange] = []
        for field_name, (new_value, confidence) in incoming.items():
            old_value = getattr(candidate, field_name)
            apply = strategy is IdentityUpdateStrategy.OVERWRITE_NON_NULL or (
                strategy is IdentityUpdateStrategy.FILL_EMPTY and old_value in {None, ""}
            )
            if strategy is IdentityUpdateStrategy.KEEP_EXISTING:
                reason = "keep_existing"
            elif not apply:
                reason = "existing_value_preserved"
            else:
                reason = strategy.value
            changes.append(
                IdentityChange(
                    field_name,
                    old_value,
                    new_value,
                    "update" if apply and old_value != new_value else "unchanged",
                    reason,
                    confidence,
                )
            )
        return changes

    @staticmethod
    def _collection_diff(
        section: str,
        existing: Sequence[TModel],
        incoming: Sequence[TDomain],
        model_key: Callable[[TModel], str],
        domain_key: Callable[[TDomain], str],
        sections: frozenset[str],
        mode: EnrichmentImportMode,
    ) -> CollectionDiff:
        existing_keys = {model_key(item) for item in existing}
        incoming_keys = {domain_key(item) for item in incoming}
        deletes = (
            len(existing_keys - incoming_keys)
            if mode is EnrichmentImportMode.REPLACE_ALL
            or (mode is EnrichmentImportMode.REPLACE_SECTIONS and section in sections)
            else 0
        )
        return CollectionDiff(
            section,
            len(incoming_keys - existing_keys),
            len(incoming_keys & existing_keys),
            deletes,
            len(existing_keys & incoming_keys),
        )

    @staticmethod
    def _experience_model_key(item: CandidateExperience) -> str:
        if item.external_key:
            return f"external:{(item.source or '').casefold()}:{item.external_key.casefold()}"
        return experience_fingerprint(CandidateEnrichmentService._experience_domain(item))

    @staticmethod
    def _experience_key(item: EnrichedExperience) -> str:
        if item.external_key:
            return f"external:{item.source.casefold()}:{item.external_key.casefold()}"
        return experience_fingerprint(item)

    @staticmethod
    def _select_current_experience(
        experiences: Sequence[EnrichedExperience],
    ) -> EnrichedExperience | None:
        current = [item for item in experiences if item.is_current]
        if not current:
            return None
        return max(
            current,
            key=lambda item: (item.start_date or date.min, -item.sort_order),
        )

    @classmethod
    def _project_experiences(
        cls,
        existing: Sequence[CandidateExperience],
        incoming: Sequence[EnrichedExperience],
        payload: CandidateEnrichmentImportRequest,
    ) -> list[EnrichedExperience]:
        projected = {
            cls._experience_model_key(item): cls._experience_domain(item) for item in existing
        }
        incoming_values = {cls._experience_key(item): item for item in incoming}
        if payload.import_mode is EnrichmentImportMode.REPLACE_ALL or (
            payload.import_mode is EnrichmentImportMode.REPLACE_SECTIONS
            and "experiences" in payload.model_fields_set
        ):
            return list(incoming_values.values())
        projected.update(incoming_values)
        return list(projected.values())

    @staticmethod
    def _experience_domain(item: CandidateExperience) -> EnrichedExperience:
        return EnrichedExperience(
            item.position_title_raw,
            item.external_key,
            item.position_title_normalized,
            item.company_name,
            item.company_url,
            item.employment_type,
            item.location,
            item.start_date,
            item.end_date,
            item.is_current,
            item.duration_months,
            item.description,
            tuple(str(v) for v in item.skills_detected),
            item.industry_detected,
            item.confidence,
            item.source or "manual",
            item.sort_order,
        )

    @staticmethod
    def _education_key(item: EnrichedEducation) -> str:
        if item.external_key:
            return f"external:{item.source}:{item.external_key}"
        return "|".join(
            (
                item.institution_name.casefold(),
                (item.field_of_study_normalized or ""),
                (item.degree or "").casefold(),
                str(item.start_year or ""),
                str(item.end_year or ""),
            )
        )

    @staticmethod
    def _education_model_key(item: CandidateEducation) -> str:
        return CandidateEnrichmentService._education_key(
            EnrichedEducation(
                item.institution_name,
                item.external_key,
                item.degree,
                item.field_of_study,
                item.field_of_study_normalized,
                item.start_year,
                item.end_year,
                item.grade,
                item.description,
                item.confidence,
                item.source or "manual",
                item.sort_order,
            )
        )

    @staticmethod
    def _certification_key(item: EnrichedCertification) -> str:
        if item.external_key:
            return f"external:{item.source}:{item.external_key}"
        if item.credential_id:
            return f"credential:{item.credential_id.casefold()}"
        return "|".join(
            (
                item.name.casefold(),
                (item.issuer or "").casefold(),
                item.issue_date.isoformat() if item.issue_date else "",
            )
        )

    @staticmethod
    def _certification_model_key(item: CandidateCertification) -> str:
        return CandidateEnrichmentService._certification_key(
            EnrichedCertification(
                item.name,
                item.external_key,
                item.issuer,
                item.issue_date,
                item.expiration_date,
                item.credential_id,
                item.credential_url,
                item.source or "manual",
                item.confidence,
            )
        )

    @staticmethod
    def _skill_key(item: CandidateSkill | EnrichedSkill) -> str:
        return f"{item.normalized_name}|{item.source.value}"

    @staticmethod
    def _language_key(item: CandidateLanguage | EnrichedLanguage) -> str:
        return item.language_normalized

    @staticmethod
    def _experience_values(item: EnrichedExperience) -> dict[str, object]:
        values = asdict(item)
        values["skills_detected"] = list(item.skills_detected)
        return values

    @staticmethod
    def _education_values(item: EnrichedEducation) -> dict[str, object]:
        return asdict(item)

    @staticmethod
    def _skill_values(item: EnrichedSkill) -> dict[str, object]:
        return asdict(item)

    @staticmethod
    def _certification_values(item: EnrichedCertification) -> dict[str, object]:
        return asdict(item)

    @staticmethod
    def _language_values(item: EnrichedLanguage) -> dict[str, object]:
        return asdict(item)

    @staticmethod
    def _projected_quality(
        candidate: Candidate,
        changes: Sequence[IdentityChange],
        experiences: CollectionDiff,
        educations: CollectionDiff,
        skills: CollectionDiff,
    ) -> float:
        values = {change.field: change.new_value for change in changes if change.action == "update"}
        quality = CandidateQualityInput(
            full_name=cast(str | None, values.get("full_name", candidate.full_name)),
            normalized_profile_url=candidate.normalized_profile_url,
            headline=cast(str | None, values.get("headline", candidate.headline)),
            location_raw=cast(str | None, values.get("location_raw", candidate.location_raw)),
            city=cast(str | None, values.get("city", candidate.city)),
            country=cast(str | None, values.get("country", candidate.country)),
            current_title=cast(str | None, values.get("current_title", candidate.current_title)),
            current_company=cast(
                str | None, values.get("current_company", candidate.current_company)
            ),
            about=cast(str | None, values.get("about", candidate.about)),
            discovery_snippet=candidate.discovery_snippet,
            experience_count=len(candidate.experiences)
            + experiences.create_count
            - experiences.delete_count,
            education_count=len(candidate.educations)
            + educations.create_count
            - educations.delete_count,
            skill_count=len(candidate.skills) + skills.create_count - skills.delete_count,
        )
        return calculate_candidate_quality(quality).total_score

    @staticmethod
    def _quality(candidate: Candidate, diff: CandidateEnrichmentDiff) -> QualityBreakdown:
        return calculate_candidate_quality(
            CandidateQualityInput(
                full_name=candidate.full_name,
                normalized_profile_url=candidate.normalized_profile_url,
                headline=candidate.headline,
                location_raw=candidate.location_raw,
                city=candidate.city,
                country=candidate.country,
                current_title=candidate.current_title,
                current_company=candidate.current_company,
                about=candidate.about,
                discovery_snippet=candidate.discovery_snippet,
                experience_count=len(candidate.experiences)
                + diff.experiences.create_count
                - diff.experiences.delete_count,
                education_count=len(candidate.educations)
                + diff.educations.create_count
                - diff.educations.delete_count,
                skill_count=len(candidate.skills)
                + diff.skills.create_count
                - diff.skills.delete_count,
            )
        )

    @staticmethod
    def _profile_status(payload: CandidateEnrichmentImportRequest) -> CandidateProfileStatus:
        return (
            CandidateProfileStatus.SCRAPED
            if payload.mode is EnrichmentMode.DEEP and not payload.is_partial
            else CandidateProfileStatus.PARTIAL
        )

    @staticmethod
    def _run_start_data(
        candidate: Candidate,
        prepared: PreparedEnrichment,
        payload: CandidateEnrichmentImportRequest,
        now: datetime,
    ) -> dict[str, object]:
        counts = {
            name: len(getattr(prepared, name))
            for name in ("experiences", "educations", "skills", "certifications", "languages")
        }
        return {
            "candidate_id": candidate.id,
            "provider": payload.provider,
            "mode": payload.mode,
            "status": CandidateEnrichmentStatus.RUNNING,
            "parser_version": payload.parser_version,
            "requested_sections": sorted(prepared.sections),
            "completed_sections": [],
            "warning_codes": payload.warnings,
            "error_codes": [],
            "input_summary": {
                "section_count": len(prepared.sections),
                "item_counts": counts,
                "mode": payload.mode.value,
            },
            "result_summary": {},
            "data_quality_before": candidate.data_quality_score,
            "started_at": now,
        }

    @staticmethod
    def _run_complete_data(
        run: CandidateEnrichmentRun,
        diff: CandidateEnrichmentDiff,
        candidate: Candidate,
        prepared: PreparedEnrichment,
        payload: CandidateEnrichmentImportRequest,
        now: datetime,
    ) -> dict[str, object]:
        values: dict[str, object] = {
            "completed_at": now,
            "completed_sections": sorted(prepared.sections),
            "data_quality_after": candidate.data_quality_score,
            "result_summary": {
                "profile_status": candidate.profile_status.value,
                "is_partial": payload.is_partial,
            },
        }
        for singular, section_diff in (
            ("experience", diff.experiences),
            ("education", diff.educations),
            ("skill", diff.skills),
            ("certification", diff.certifications),
            ("language", diff.languages),
        ):
            values[f"created_{singular}_count"] = section_diff.create_count
            values[f"updated_{singular}_count"] = section_diff.update_count
            values[f"deleted_{singular}_count"] = section_diff.delete_count
        return values

    async def _record_failed_run(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        payload: CandidateEnrichmentImportRequest,
        quality_before: float,
        started_at: datetime,
    ) -> None:
        try:
            now = datetime.now(UTC)
            await self.run_repository.create(
                session,
                data={
                    "candidate_id": candidate_id,
                    "provider": payload.provider,
                    "mode": payload.mode,
                    "status": CandidateEnrichmentStatus.FAILED,
                    "parser_version": payload.parser_version,
                    "requested_sections": [],
                    "completed_sections": [],
                    "warning_codes": [],
                    "error_codes": ["persistence_error"],
                    "input_summary": {},
                    "result_summary": {},
                    "data_quality_before": quality_before,
                    "started_at": started_at,
                    "completed_at": now,
                },
            )
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
