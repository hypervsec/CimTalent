from typing import Protocol, TypeVar

from app.domain.linkedin.types import ParserResult
from app.integrations.linkedin.parser_context import ParserContext

T = TypeVar("T", covariant=True)


class LinkedInParser(Protocol[T]):
    def parse(self, context: ParserContext) -> ParserResult[T]: ...
