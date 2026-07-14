from app.domain.enrichment.types import ExtractedText
from app.domain.linkedin.types import ParserResult
from app.integrations.linkedin.parser_context import ParserContext
from app.integrations.linkedin.parsers.common import text


class AboutParser:
    def parse(self, context: ParserContext) -> ParserResult[ExtractedText]:
        section, selector = context.selector_registry.first(context.soup, "about.section")
        if section is None:
            return ParserResult(warnings=("section_empty",), is_partial=True)
        content, content_selector = context.selector_registry.first(section, "about.content")
        value = text(content)
        if value:
            value = value[:20_000]
            return ParserResult(
                value=ExtractedText(value, "linkedin", 0.95),
                selectors_used=tuple(x for x in (selector, content_selector) if x),
            )
        return ParserResult(
            warnings=("section_empty",),
            is_partial=True,
            selectors_used=tuple(x for x in (selector, content_selector) if x),
        )
