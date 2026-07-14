from app.domain.jobs.parser_types import JobParseInput, ParsedJobData
from app.parsers.jobs.orchestrator import PARSER_VERSION, JobParserOrchestrator


class RuleBasedJobParser:
    def __init__(self, orchestrator: JobParserOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or JobParserOrchestrator()

    @property
    def version(self) -> str:
        return PARSER_VERSION

    def parse(self, data: JobParseInput) -> ParsedJobData:
        return self.orchestrator.parse(data)
