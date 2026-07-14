from collections.abc import Mapping, Sequence
from datetime import datetime
from difflib import SequenceMatcher
from uuid import UUID

from app.domain.candidates.normalizers import candidate_name_key, clean_text
from app.domain.candidates.types import CandidateFieldStrategy, DuplicateCandidateSuggestion

MERGE_FIELDS = (
    "primary_profile_url",
    "normalized_profile_url",
    "profile_slug",
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
    "last_scraped_at",
)


def select_merged_fields(
    target: Mapping[str, object],
    sources: Sequence[Mapping[str, object]],
    strategy: CandidateFieldStrategy,
    explicit_values: Mapping[str, object] | None = None,
) -> tuple[dict[str, object], list[str]]:
    candidates = [target, *sources]
    merged: dict[str, object] = {}
    conflicts: list[str] = []
    for field_name in MERGE_FIELDS:
        values = [record.get(field_name) for record in candidates]
        non_empty = [value for value in values if _meaningful(value)]
        if len({_hashable(value) for value in non_empty}) > 1:
            conflicts.append(field_name)
        if strategy is CandidateFieldStrategy.PREFER_NEWEST:
            ordered = sorted(
                candidates,
                key=_updated_at,
                reverse=True,
            )
            merged[field_name] = next(
                (
                    record.get(field_name)
                    for record in ordered
                    if _meaningful(record.get(field_name))
                ),
                None,
            )
        else:
            merged[field_name] = non_empty[0] if non_empty else None
    for field_name, value in (explicit_values or {}).items():
        if field_name in MERGE_FIELDS:
            merged[field_name] = value
    return merged, conflicts


def duplicate_suggestion(
    *,
    candidate_id: UUID,
    base: Mapping[str, str | None],
    other: Mapping[str, str | None],
) -> DuplicateCandidateSuggestion | None:
    matched: list[str] = []
    reasons: list[str] = []
    score = 0.0
    if _equal(base.get("normalized_profile_url"), other.get("normalized_profile_url")):
        score = 1.0
        matched.append("normalized_profile_url")
        reasons.append("exact_profile_url")
    elif _equal(base.get("profile_slug"), other.get("profile_slug")):
        score = 0.99
        matched.append("profile_slug")
        reasons.append("exact_linkedin_slug")
    else:
        same_name = (
            candidate_name_key(base.get("full_name")) == candidate_name_key(other.get("full_name"))
            and candidate_name_key(base.get("full_name")) is not None
        )
        same_headline = _equal(base.get("headline"), other.get("headline"))
        same_city = _equal(base.get("city"), other.get("city"))
        same_company = _equal(base.get("current_company"), other.get("current_company"))
        if same_name and same_headline and same_city:
            score = 0.95
            matched.extend(("full_name", "headline", "city"))
            reasons.append("exact_name_headline_city")
        elif same_name and same_company:
            score = 0.9
            matched.extend(("full_name", "current_company"))
            reasons.append("exact_name_company")
        else:
            left = candidate_name_key(base.get("full_name"))
            right = candidate_name_key(other.get("full_name"))
            similarity = SequenceMatcher(None, left or "", right or "").ratio()
            if similarity >= 0.85 and (same_headline or same_city):
                score = min(0.89, 0.65 + similarity * 0.2)
                matched.append("fuzzy_full_name")
                if same_headline:
                    matched.append("headline")
                if same_city:
                    matched.append("city")
                reasons.append("fuzzy_name_with_supporting_fields")
    if score == 0.0:
        return None
    return DuplicateCandidateSuggestion(candidate_id, round(score, 4), matched, reasons)


def _equal(left: str | None, right: str | None) -> bool:
    clean_left = clean_text(left)
    clean_right = clean_text(right)
    return (
        clean_left is not None
        and clean_right is not None
        and clean_left.casefold() == clean_right.casefold()
    )


def _meaningful(value: object) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _hashable(value: object) -> object:
    return (
        value if isinstance(value, (str, int, float, bool, datetime, type(None))) else repr(value)
    )


def _updated_at(item: Mapping[str, object]) -> float:
    value = item.get("updated_at")
    return value.timestamp() if isinstance(value, datetime) else float("-inf")
