from app.db.enums import CandidateSkillSource
from app.domain.enrichment.normalizers import normalize_skill
from app.domain.enrichment.types import EnrichedSkill
from app.domain.linkedin.types import ParserResult
from app.integrations.linkedin.parser_context import ParserContext
from app.integrations.linkedin.parsers.common import endorsement_count, text


class SkillsParser:
    def parse(self, context: ParserContext) -> ParserResult[EnrichedSkill]:
        section, selector = context.selector_registry.first(context.soup, "skills.list")
        if section is None:
            return ParserResult(warnings=("section_empty",), is_partial=True)
        items, item_selector = context.selector_registry.all(section, "skills.item")
        result: list[EnrichedSkill] = []
        seen: set[str] = set()
        for item in items[: context.limits.skills]:
            name = text(item.select_one("[data-field='name'], .skill-name, h3, h4"))
            if not name:
                continue
            skill = normalize_skill(
                EnrichedSkill(
                    raw_name=name,
                    normalized_name="",
                    category=None,
                    endorsement_count=endorsement_count(text(item)),
                    source=CandidateSkillSource.PROFILE_SKILL,
                    confidence=0.98,
                )
            )
            if skill.normalized_name not in seen:
                seen.add(skill.normalized_name)
                result.append(skill)
        return ParserResult(
            items=tuple(result), selectors_used=tuple(x for x in (selector, item_selector) if x)
        )
