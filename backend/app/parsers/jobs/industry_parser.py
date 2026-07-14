from types import MappingProxyType

from app.db.enums import RequirementType
from app.domain.jobs.parser_types import (
    EvidenceUnit,
    ParsedRequirement,
    ParserFragment,
    requirement_weight,
)
from app.domain.jobs.taxonomies import INDUSTRIES
from app.parsers.jobs.phrase_matcher import compile_phrase_patterns, find_phrase_matches

INDUSTRY_PATTERNS = compile_phrase_patterns(tuple(INDUSTRIES))
INDUSTRY_VALUES = MappingProxyType(
    {phrase: (value, "industry") for phrase, value in INDUSTRIES.items()}
)


class IndustryParser:
    def parse(self, units: tuple[EvidenceUnit, ...]) -> ParserFragment:
        requirements: list[ParsedRequirement] = []
        values: list[str] = []
        for unit in units:
            for match in find_phrase_matches(unit.text, INDUSTRY_PATTERNS, INDUSTRY_VALUES):
                requirements.append(
                    ParsedRequirement(
                        type=RequirementType.INDUSTRY,
                        raw_value=match.raw,
                        normalized_value=match.normalized,
                        importance=unit.importance,
                        weight=requirement_weight(unit.importance),
                        confidence=0.85,
                        evidence_text=unit.text,
                        evidence_start=unit.start,
                        evidence_end=unit.end,
                    )
                )
                values.append(match.normalized)
        return ParserFragment(requirements=tuple(requirements), values=tuple(values))
