from dataclasses import dataclass

from app.domain.candidates.constants import QUALITY_WEIGHTS
from app.domain.candidates.normalizers import clean_text, normalize_candidate_name
from app.sourcing.profile_url_normalizer import normalize_url


@dataclass(frozen=True, slots=True)
class CandidateQualityInput:
    full_name: str | None = None
    normalized_profile_url: str | None = None
    headline: str | None = None
    location_raw: str | None = None
    city: str | None = None
    country: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    about: str | None = None
    discovery_snippet: str | None = None
    experience_count: int = 0
    education_count: int = 0
    skill_count: int = 0


@dataclass(frozen=True, slots=True)
class QualityBreakdown:
    total_score: float
    field_scores: dict[str, int]
    missing_fields: list[str]
    warnings: list[str]


def calculate_candidate_quality(data: CandidateQualityInput) -> QualityBreakdown:
    present = {
        "full_name": normalize_candidate_name(data.full_name) is not None,
        "normalized_profile_url": _is_candidate_profile_url(data.normalized_profile_url),
        "headline": clean_text(data.headline) is not None,
        "location": any(
            clean_text(item) is not None for item in (data.location_raw, data.city, data.country)
        ),
        "current_title": clean_text(data.current_title) is not None,
        "current_company": clean_text(data.current_company) is not None,
        "about": clean_text(data.about) is not None,
        "discovery_snippet": clean_text(data.discovery_snippet) is not None,
        "experience": data.experience_count > 0,
        "education": data.education_count > 0,
        "skills": data.skill_count >= 3,
    }
    scores = {key: weight if present[key] else 0 for key, weight in QUALITY_WEIGHTS.items()}
    warnings: list[str] = []
    if clean_text(data.full_name) and not present["full_name"]:
        warnings.append("placeholder_name")
    if clean_text(data.normalized_profile_url) and not present["normalized_profile_url"]:
        warnings.append("invalid_candidate_profile_url")
    return QualityBreakdown(
        total_score=float(max(0, min(100, sum(scores.values())))),
        field_scores=scores,
        missing_fields=[key for key, value in present.items() if not value],
        warnings=warnings,
    )


def _is_candidate_profile_url(value: str | None) -> bool:
    if value is None:
        return False
    normalized = normalize_url(value)
    if normalized is None:
        return False
    if normalized.source_domain == "linkedin.com":
        return normalized.candidate_profile_slug is not None
    return normalized.source_domain not in {"google.com", "www.google.com", "bing.com"}
