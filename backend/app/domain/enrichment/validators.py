from datetime import date

from app.domain.enrichment.constants import MAX_EVIDENCE_LENGTH
from app.domain.enrichment.exceptions import CandidateEnrichmentValidationError


def validate_confidence(value: float) -> float:
    if not 0 <= value <= 1:
        raise CandidateEnrichmentValidationError("confidence must be between 0 and 1.")
    return value


def validate_required_text(value: str, field_name: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise CandidateEnrichmentValidationError(f"{field_name} cannot be empty.")
    return cleaned


def validate_evidence(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if len(cleaned) > MAX_EVIDENCE_LENGTH:
        raise CandidateEnrichmentValidationError("evidence is too long.")
    if "<html" in cleaned.casefold() or "<!doctype" in cleaned.casefold():
        raise CandidateEnrichmentValidationError("Full HTML evidence is not accepted.")
    return cleaned or None


def validate_date_range(start: date | None, end: date | None) -> None:
    if start is not None and end is not None and end < start:
        raise CandidateEnrichmentValidationError("end date cannot precede start date.")


def validate_year_range(start: int | None, end: int | None) -> None:
    if any(year is not None and not 1900 <= year <= 2100 for year in (start, end)):
        raise CandidateEnrichmentValidationError("education years must be between 1900 and 2100.")
    if start is not None and end is not None and end < start:
        raise CandidateEnrichmentValidationError("end year cannot precede start year.")
