from typing import Protocol

from app.domain.jobs.parser_types import JobParseInput, ParsedJobData


class JobParser(Protocol):
    @property
    def version(self) -> str: ...

    def parse(self, data: JobParseInput) -> ParsedJobData: ...
