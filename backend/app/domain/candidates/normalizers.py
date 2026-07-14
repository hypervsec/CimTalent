import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.domain.candidates.constants import (
    LINKEDIN_BLOCKED_PATHS,
    PLACEHOLDER_NAMES,
    SEARCH_ENGINE_DOMAINS,
)
from app.domain.candidates.types import (
    CandidateDiscoveryInput,
    CandidateEligibilityResult,
    CandidateEligibilitySource,
)

WHITESPACE_RE = re.compile(r"\s+")
LINKEDIN_NAME_SUFFIX_RE = re.compile(r"\s*(?:[-|]\s*LinkedIn|\|\s*LinkedIn)\s*$", re.I)
TURKISH_PROFILE_SUFFIX_RE = re.compile(r"\s+adl[ıi]\s+kullan[ıi]c[ıi]n[ıi]n\s+profili\s*$", re.I)
HONORIFIC_RE = re.compile(r"^(?:dr\.?|mr\.?|ms\.?|mrs\.?)\s+", re.I)
HEADLINE_LINKEDIN_SUFFIX_RE = re.compile(r"\s*(?:\||-)\s*LinkedIn\s*$", re.I)
AT_COMPANY_RE = re.compile(r"^(?P<title>.+?)\s+(?:at|@)\s+(?P<company>[^|]+)$", re.I)


@dataclass(frozen=True, slots=True)
class LocationNormalization:
    location_raw: str | None
    city: str | None
    country: str | None


@dataclass(frozen=True, slots=True)
class HeadlineIdentity:
    cleaned_headline: str | None
    current_title: str | None
    current_company: str | None
    confidence: float


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    clean = WHITESPACE_RE.sub(" ", unicodedata.normalize("NFKC", value)).strip()
    return clean or None


def normalize_candidate_name(value: str | None, *, remove_honorific: bool = True) -> str | None:
    clean = clean_text(value)
    if clean is None:
        return None
    clean = LINKEDIN_NAME_SUFFIX_RE.sub("", clean)
    clean = TURKISH_PROFILE_SUFFIX_RE.sub("", clean)
    if remove_honorific:
        clean = HONORIFIC_RE.sub("", clean)
    clean = clean_text(clean)
    if clean is None or clean.casefold() in PLACEHOLDER_NAMES:
        return None
    return clean


def candidate_name_key(value: str | None) -> str | None:
    clean = normalize_candidate_name(value)
    return clean.casefold() if clean is not None else None


def normalize_candidate_location(value: str | None) -> LocationNormalization:
    raw = clean_text(value)
    if raw is None:
        return LocationNormalization(None, None, None)
    pieces = [item.strip() for item in raw.split(",") if item.strip()]
    folded = [item.casefold() for item in pieces]
    country: str | None = None
    city: str | None = None
    country_tokens = {"turkey", "türkiye", "turkiye"}
    city_names = {
        "bursa": "Bursa",
        "istanbul": "Istanbul",
        "i̇stanbul": "Istanbul",
        "kocaeli": "Kocaeli",
        "gemlik": "Gemlik",
    }
    if any(item in country_tokens for item in folded):
        country = "Turkey"
    for item in folded:
        if item in city_names:
            city = city_names[item]
            break
    if len(pieces) == 1 and folded[0] in country_tokens:
        city = None
    return LocationNormalization(raw, city, country)


def parse_headline_identity(value: str | None) -> HeadlineIdentity:
    cleaned = clean_text(value)
    if cleaned is None:
        return HeadlineIdentity(None, None, None, 0.0)
    cleaned = clean_text(HEADLINE_LINKEDIN_SUFFIX_RE.sub("", cleaned))
    if cleaned is None:
        return HeadlineIdentity(None, None, None, 0.0)
    match = AT_COMPANY_RE.match(cleaned)
    if match is not None:
        title = clean_text(match.group("title"))
        company = clean_text(match.group("company"))
        return HeadlineIdentity(cleaned, title, company, 0.95)
    if "|" in cleaned:
        first = clean_text(cleaned.split("|", maxsplit=1)[0])
        return HeadlineIdentity(cleaned, first, None, 0.7)
    if "student" in cleaned.casefold() or "öğrenci" in cleaned.casefold():
        return HeadlineIdentity(cleaned, None, None, 0.4)
    return HeadlineIdentity(cleaned, None, None, 0.3)


def evaluate_candidate_eligibility(
    data: CandidateDiscoveryInput,
) -> CandidateEligibilityResult:
    try:
        parsed = urlsplit(data.normalized_url)
    except ValueError:
        parsed = urlsplit("")
    host = (parsed.hostname or "").casefold()
    path = parsed.path.casefold()
    if parsed.scheme not in {"http", "https"} or not host:
        return CandidateEligibilityResult(
            False, CandidateEligibilitySource.UNSUPPORTED, 0.0, "invalid_profile_url"
        )
    if host in SEARCH_ENGINE_DOMAINS:
        return CandidateEligibilityResult(
            False, CandidateEligibilitySource.UNSUPPORTED, 0.0, "search_engine_result"
        )
    is_linkedin = host == "linkedin.com" or host.endswith(".linkedin.com")
    if is_linkedin:
        if any(path.startswith(prefix) for prefix in LINKEDIN_BLOCKED_PATHS):
            return CandidateEligibilityResult(
                False, CandidateEligibilitySource.UNSUPPORTED, 0.0, "non_person_linkedin_page"
            )
        if data.candidate_profile_slug and path.startswith("/in/"):
            confidence = 0.98 if normalize_candidate_name(data.displayed_name) else 0.9
            return CandidateEligibilityResult(
                True,
                CandidateEligibilitySource.LINKEDIN_PROFILE,
                confidence,
                "linkedin_profile_url",
            )
        return CandidateEligibilityResult(
            False, CandidateEligibilitySource.UNSUPPORTED, 0.0, "non_profile_linkedin_url"
        )
    meaningful_metadata = bool(
        normalize_candidate_name(data.displayed_name)
        or clean_text(data.displayed_headline)
        or clean_text(data.title)
    )
    if host in {"github.com", "www.github.com"} and len(path.strip("/").split("/")) == 1:
        return CandidateEligibilityResult(
            meaningful_metadata,
            CandidateEligibilitySource.GITHUB_PROFILE,
            0.8 if meaningful_metadata else 0.3,
            "github_user_profile" if meaningful_metadata else "missing_person_metadata",
        )
    if meaningful_metadata:
        return CandidateEligibilityResult(
            True, CandidateEligibilitySource.PERSONAL_PROFILE, 0.7, "personal_profile_metadata"
        )
    return CandidateEligibilityResult(
        False, CandidateEligibilitySource.UNSUPPORTED, 0.2, "missing_person_metadata"
    )
