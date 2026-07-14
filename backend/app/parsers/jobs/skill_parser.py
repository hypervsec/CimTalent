from types import MappingProxyType

from app.db.enums import RequirementType
from app.domain.jobs.parser_types import (
    EvidenceUnit,
    ParsedRequirement,
    ParserFragment,
    requirement_weight,
)
from app.domain.jobs.taxonomies import SKILL_TAXONOMY
from app.parsers.jobs.phrase_matcher import compile_phrase_patterns, find_phrase_matches

SKILL_PATTERNS = compile_phrase_patterns(tuple(SKILL_TAXONOMY))
SKILL_VALUES = MappingProxyType(
    {phrase: (entry.normalized, entry.category) for phrase, entry in SKILL_TAXONOMY.items()}
)


class SkillParser:
    def parse(self, units: tuple[EvidenceUnit, ...]) -> ParserFragment:
        requirements: list[ParsedRequirement] = []
        values: list[str] = []
        for unit in units:
            for match in find_phrase_matches(unit.text, SKILL_PATTERNS, SKILL_VALUES):
                requirements.append(
                    ParsedRequirement(
                        type=RequirementType.SKILL,
                        raw_value=match.raw,
                        normalized_value=match.normalized,
                        importance=unit.importance,
                        weight=requirement_weight(unit.importance),
                        confidence=match.confidence,
                        evidence_text=unit.text,
                        evidence_start=unit.start,
                        evidence_end=unit.end,
                    )
                )
                values.append(match.normalized)
        return ParserFragment(requirements=tuple(requirements), values=tuple(values))
