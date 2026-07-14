from app.domain.enrichment.types import EnrichedCandidateIdentity, ExtractedBoolean, ExtractedText
from app.domain.linkedin.exceptions import SelectorChangedError
from app.domain.linkedin.types import ParserResult
from app.integrations.linkedin.parser_context import ParserContext
from app.integrations.linkedin.parsers.common import text


class TopCardParser:
    def parse(self, context: ParserContext) -> ParserResult[EnrichedCandidateIdentity]:
        card, card_selector = context.selector_registry.first(context.soup, "profile.top_card")
        if card is None:
            raise SelectorChangedError(
                "LinkedIn profile top-card shell was not found.", selector_group="profile.top_card"
            )
        name_node, name_selector = context.selector_registry.first(card, "top_card.name")
        name = text(name_node)
        if not name:
            raise SelectorChangedError(
                "LinkedIn profile name was not found.", selector_group="top_card.name"
            )
        headline_node, headline_selector = context.selector_registry.first(
            card, "top_card.headline"
        )
        location_node, location_selector = context.selector_registry.first(
            card, "top_card.location"
        )
        open_node, open_selector = context.selector_registry.first(card, "top_card.open_to_work")
        headline = text(headline_node)
        location = text(location_node)
        selectors = tuple(
            x
            for x in (
                card_selector,
                name_selector,
                headline_selector,
                location_selector,
                open_selector,
            )
            if x
        )
        return ParserResult(
            value=EnrichedCandidateIdentity(
                full_name=ExtractedText(name, "linkedin", 0.98),
                headline=ExtractedText(headline, "linkedin", 0.98) if headline else None,
                location_raw=ExtractedText(location, "linkedin", 0.98) if location else None,
                open_to_work=ExtractedBoolean(True, "linkedin", 0.95) if open_node else None,
            ),
            selectors_used=selectors,
            warnings=tuple(
                x
                for x, node in (
                    ("headline_missing", headline_node),
                    ("location_missing", location_node),
                )
                if node is None
            ),
        )
