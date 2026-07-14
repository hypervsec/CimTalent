from types import MappingProxyType

from app.db.enums import RequirementType
from app.domain.jobs.normalizers import normalize_for_matching
from app.domain.jobs.parser_types import (
    EvidenceUnit,
    ParsedRequirement,
    ParserFragment,
    requirement_weight,
)
from app.domain.jobs.taxonomies import EDUCATION_FIELDS, EDUCATION_LEVELS
from app.parsers.jobs.phrase_matcher import compile_phrase_patterns, find_phrase_matches

FIELD_PATTERNS = compile_phrase_patterns(tuple(EDUCATION_FIELDS))
FIELD_VALUES = MappingProxyType(
    {phrase: (value, "field") for phrase, value in EDUCATION_FIELDS.items()}
)
LEVEL_PATTERNS = compile_phrase_patterns(tuple(EDUCATION_LEVELS))
LEVEL_VALUES = MappingProxyType(
    {phrase: (value, "level") for phrase, value in EDUCATION_LEVELS.items()}
)


class EducationParser:
    def parse(self, units: tuple[EvidenceUnit, ...]) -> ParserFragment:
        requirements: list[ParsedRequirement] = []
        values: list[str] = []
        warnings: list[str] = []
        for unit in units:
            normalized_text = normalize_for_matching(unit.text)
            if "ilgili böl" in normalized_text or "related field" in normalized_text:
                warnings.append("related_departments_phrase_detected")
            matches = (
                *find_phrase_matches(unit.text, FIELD_PATTERNS, FIELD_VALUES),
                *find_phrase_matches(unit.text, LEVEL_PATTERNS, LEVEL_VALUES),
            )
            for match in matches:
                normalized = f"{match.category}:{match.normalized}"
                requirements.append(
                    ParsedRequirement(
                        type=RequirementType.EDUCATION,
                        raw_value=match.raw,
                        normalized_value=normalized,
                        importance=unit.importance,
                        weight=requirement_weight(unit.importance),
                        confidence=match.confidence,
                        evidence_text=unit.text,
                        evidence_start=unit.start,
                        evidence_end=unit.end,
                    )
                )
                values.append(normalized)
        return ParserFragment(
            requirements=tuple(requirements),
            values=tuple(values),
            warnings=tuple(warnings),
        )
