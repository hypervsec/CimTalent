from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from hashlib import sha256

from app.db.enums import CandidateSkillSource
from app.domain.enrichment.constants import MAX_DESCRIPTION_LENGTH
from app.domain.enrichment.exceptions import CandidateEnrichmentValidationError
from app.domain.enrichment.types import (
    EnrichedCertification,
    EnrichedEducation,
    EnrichedExperience,
    EnrichedLanguage,
    EnrichedSkill,
)
from app.domain.enrichment.validators import (
    validate_confidence,
    validate_date_range,
    validate_required_text,
    validate_year_range,
)
from app.domain.jobs.taxonomies import (
    CERTIFICATIONS,
    EDUCATION_FIELDS,
    LANGUAGE_PROFICIENCIES,
    LANGUAGES,
    SKILL_TAXONOMY,
    TITLE_ALIASES,
)
from app.sourcing.profile_url_normalizer import normalize_url

SPACE_RE = re.compile(r"\s+")
SOURCE_CONFIDENCE_CAP = {
    CandidateSkillSource.PROFILE_SKILL: 1.0,
    CandidateSkillSource.EXPERIENCE_TEXT: 0.8,
    CandidateSkillSource.ABOUT_TEXT: 0.7,
    CandidateSkillSource.INFERRED: 0.5,
    CandidateSkillSource.MANUAL: 1.0,
}


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = SPACE_RE.sub(" ", value).strip()
    return cleaned or None


def normalize_key(value: str | None) -> str | None:
    cleaned = clean_optional(value)
    return cleaned.casefold() if cleaned else None


def normalize_title(value: str) -> str:
    cleaned = validate_required_text(value, "position_title_raw")
    return TITLE_ALIASES.get(cleaned.casefold(), cleaned.casefold())


def normalize_skill_name(value: str) -> tuple[str, str | None]:
    cleaned = validate_required_text(value, "raw_name")
    entry = SKILL_TAXONOMY.get(cleaned.casefold())
    return (entry.normalized, entry.category) if entry else (cleaned.casefold(), None)


def _safe_url(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = normalize_url(value)
    if normalized is None:
        raise CandidateEnrichmentValidationError(f"{field_name} must be a safe HTTP(S) URL.")
    return normalized.value


def calculate_duration_months(start: date | None, end: date | None) -> int | None:
    if start is None or end is None:
        return None
    validate_date_range(start, end)
    return (end.year - start.year) * 12 + end.month - start.month + 1


def normalize_experience(
    item: EnrichedExperience, *, today: date | None = None
) -> EnrichedExperience:
    title = validate_required_text(item.position_title_raw, "position_title_raw")
    validate_confidence(item.confidence)
    if item.sort_order < 0:
        raise CandidateEnrichmentValidationError("sort_order cannot be negative.")
    if item.description is not None and len(item.description) > MAX_DESCRIPTION_LENGTH:
        raise CandidateEnrichmentValidationError("experience description is too long.")
    if item.duration_months is not None and item.duration_months < 0:
        raise CandidateEnrichmentValidationError("duration_months cannot be negative.")
    if item.is_current and item.end_date is not None:
        raise CandidateEnrichmentValidationError("current experience cannot have an end date.")
    validate_date_range(item.start_date, item.end_date)
    effective_end = today if item.is_current and item.start_date else item.end_date
    skills = tuple(dict.fromkeys(normalize_skill_name(skill)[0] for skill in item.skills_detected))
    calculated_duration = calculate_duration_months(item.start_date, effective_end)
    return replace(
        item,
        position_title_raw=title,
        position_title_normalized=normalize_title(title),
        external_key=normalize_key(item.external_key),
        company_name=clean_optional(item.company_name),
        company_url=_safe_url(item.company_url, "company_url"),
        employment_type=clean_optional(item.employment_type),
        location=clean_optional(item.location),
        duration_months=(
            calculated_duration if calculated_duration is not None else item.duration_months
        ),
        description=item.description.strip() if item.description else None,
        skills_detected=skills,
        source=validate_required_text(item.source, "source").casefold(),
    )


def experience_fingerprint(item: EnrichedExperience) -> str:
    values = (
        item.position_title_normalized or normalize_title(item.position_title_raw),
        normalize_key(item.company_name) or "",
        item.start_date.isoformat() if item.start_date else "",
        item.end_date.isoformat() if item.end_date else "",
        str(item.is_current),
    )
    return sha256("|".join(values).encode()).hexdigest()


def normalize_education(item: EnrichedEducation) -> EnrichedEducation:
    institution = validate_required_text(item.institution_name, "institution_name")
    validate_confidence(item.confidence)
    validate_year_range(item.start_year, item.end_year)
    if item.sort_order < 0:
        raise CandidateEnrichmentValidationError("sort_order cannot be negative.")
    field = clean_optional(item.field_of_study)
    normalized_field = EDUCATION_FIELDS.get(field.casefold(), field.casefold()) if field else None
    return replace(
        item,
        institution_name=institution,
        external_key=normalize_key(item.external_key),
        degree=clean_optional(item.degree),
        field_of_study=field,
        field_of_study_normalized=normalized_field,
        source=validate_required_text(item.source, "source").casefold(),
    )


def normalize_skill(item: EnrichedSkill) -> EnrichedSkill:
    normalized, category = normalize_skill_name(item.raw_name)
    if item.endorsement_count is not None and item.endorsement_count < 0:
        raise CandidateEnrichmentValidationError("endorsement_count cannot be negative.")
    validate_confidence(item.confidence)
    return replace(
        item,
        raw_name=validate_required_text(item.raw_name, "raw_name"),
        normalized_name=normalized,
        category=clean_optional(item.category) or category,
        confidence=min(item.confidence, SOURCE_CONFIDENCE_CAP[item.source]),
    )


def normalize_certification(item: EnrichedCertification) -> EnrichedCertification:
    name = validate_required_text(item.name, "name")
    validate_confidence(item.confidence)
    validate_date_range(item.issue_date, item.expiration_date)
    return replace(
        item,
        name=CERTIFICATIONS.get(name.casefold(), name),
        external_key=normalize_key(item.external_key),
        issuer=clean_optional(item.issuer),
        credential_id=clean_optional(item.credential_id),
        credential_url=_safe_url(item.credential_url, "credential_url"),
        source=validate_required_text(item.source, "source").casefold(),
    )


def normalize_language(item: EnrichedLanguage) -> EnrichedLanguage:
    language = validate_required_text(item.language, "language")
    validate_confidence(item.confidence)
    normalized = LANGUAGES.get(language.casefold(), language.casefold())
    proficiency = clean_optional(item.proficiency)
    if proficiency:
        proficiency = LANGUAGE_PROFICIENCIES.get(proficiency.casefold(), proficiency.casefold())
    return replace(
        item,
        language=language,
        language_normalized=normalized,
        proficiency=proficiency,
        source=validate_required_text(item.source, "source").casefold(),
    )


def total_experience_months(
    experiences: tuple[EnrichedExperience, ...] | list[EnrichedExperience], *, today: date
) -> int:
    months: set[tuple[int, int]] = set()
    duration_fallback = 0
    seen: set[str] = set()
    for raw in experiences:
        item = normalize_experience(raw, today=today)
        fingerprint = experience_fingerprint(item)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        end = today if item.is_current else item.end_date
        if item.start_date is not None and end is not None:
            cursor_year, cursor_month = item.start_date.year, item.start_date.month
            while (cursor_year, cursor_month) <= (end.year, end.month):
                months.add((cursor_year, cursor_month))
                cursor_month += 1
                if cursor_month == 13:
                    cursor_year, cursor_month = cursor_year + 1, 1
        elif item.start_date is None and item.duration_months is not None:
            duration_fallback += max(0, item.duration_months)
    return len(months) + duration_fallback
