from dataclasses import dataclass

from bs4 import BeautifulSoup

from app.domain.enrichment.enums import EnrichmentMode
from app.domain.linkedin.types import ParserLimits
from app.integrations.linkedin.selector_registry import SelectorRegistry


@dataclass(frozen=True, slots=True)
class ParserContext:
    soup: BeautifulSoup
    source_url: str
    locale_hint: str | None
    mode: EnrichmentMode
    selector_registry: SelectorRegistry
    parser_version: str
    limits: ParserLimits
    correlation_id: str | None = None
