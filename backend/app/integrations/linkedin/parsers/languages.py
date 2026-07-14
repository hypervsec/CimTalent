from app.domain.enrichment.normalizers import normalize_language
from app.domain.enrichment.types import EnrichedLanguage
from app.domain.linkedin.types import ParserResult
from app.integrations.linkedin.parser_context import ParserContext
from app.integrations.linkedin.parsers.common import text


class LanguagesParser:
    def parse(self, context: ParserContext) -> ParserResult[EnrichedLanguage]:
        section, selector = context.selector_registry.first(context.soup, "languages.list")
        if section is None:
            return ParserResult(warnings=("section_empty",), is_partial=True)
        items, item_selector = context.selector_registry.all(section, "languages.item")
        result: list[EnrichedLanguage] = []
        seen: set[str] = set()
        for item in items[: context.limits.languages]:
            language = text(item.select_one("[data-field='name'], .language-name, h3, h4"))
            if not language:
                continue
            normalized = normalize_language(
                EnrichedLanguage(
                    language,
                    "",
                    text(item.select_one("[data-field='proficiency'], .proficiency")),
                    0.95,
                    "linkedin",
                )
            )
            if normalized.language_normalized not in seen:
                seen.add(normalized.language_normalized)
                result.append(normalized)
        return ParserResult(
            items=tuple(result), selectors_used=tuple(x for x in (selector, item_selector) if x)
        )
