from types import MappingProxyType

from app.db.enums import RequirementImportance, RequirementType
from app.domain.jobs.normalizers import normalize_for_matching
from app.domain.jobs.parser_types import (
    EvidenceUnit,
    JobParseInput,
    ParsedRequirement,
    ParserFragment,
    requirement_weight,
)
from app.domain.jobs.taxonomies import LOCATIONS
from app.parsers.jobs.phrase_matcher import compile_phrase_patterns, find_phrase_matches

LOCATION_PATTERNS = compile_phrase_patterns(tuple(LOCATIONS))
LOCATION_VALUES = MappingProxyType(
    {phrase: (value, "location") for phrase, value in LOCATIONS.items()}
)


class LocationParser:
    def parse(self, data: JobParseInput, units: tuple[EvidenceUnit, ...]) -> ParserFragment:
        requirements: list[ParsedRequirement] = []
        values: list[str] = []
        explicit = (
            (data.city, "city", 1.0),
            (data.country, "country", 1.0),
            (data.location_raw, "location", 0.95),
        )
        for raw, category, confidence in explicit:
            if raw is None or not raw.strip():
                continue
            normalized = self._normalize_explicit(raw, category)
            requirements.append(
                ParsedRequirement(
                    type=RequirementType.LOCATION,
                    raw_value=raw.strip(),
                    normalized_value=normalized,
                    importance=RequirementImportance.REQUIRED,
                    weight=1.0,
                    confidence=confidence,
                    evidence_text=raw.strip(),
                )
            )
            values.append(normalized)
        for unit in units:
            for match in find_phrase_matches(unit.text, LOCATION_PATTERNS, LOCATION_VALUES):
                importance = unit.importance
                normalized_unit = normalize_for_matching(unit.text)
                if "ikamet" in normalized_unit or "çalışabilecek" in normalized_unit:
                    importance = RequirementImportance.REQUIRED
                requirements.append(
                    ParsedRequirement(
                        type=RequirementType.LOCATION,
                        raw_value=match.raw,
                        normalized_value=match.normalized,
                        importance=importance,
                        weight=requirement_weight(importance),
                        confidence=0.9,
                        evidence_text=unit.text,
                        evidence_start=unit.start,
                        evidence_end=unit.end,
                    )
                )
                values.append(match.normalized)
        return ParserFragment(requirements=tuple(requirements), values=tuple(values))

    @staticmethod
    def _normalize_explicit(raw: str, category: str) -> str:
        normalized = normalize_for_matching(raw)
        for phrase, value in LOCATIONS.items():
            if normalize_for_matching(phrase) == normalized:
                return value
        prefix = "country" if category == "country" else "city"
        return f"{prefix}:{normalized}"
