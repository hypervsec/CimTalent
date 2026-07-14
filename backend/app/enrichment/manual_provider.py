from app.domain.enrichment.exceptions import CandidateEnrichmentStateError
from app.domain.enrichment.types import CandidateEnrichmentRequest, CandidateEnrichmentResult


class ManualEnrichmentProvider:
    """Returns a validated, structured manual result without knowing about persistence."""

    def __init__(self, result: CandidateEnrichmentResult) -> None:
        self.result = result

    async def enrich(self, request: CandidateEnrichmentRequest) -> CandidateEnrichmentResult:
        if self.result.mode is not request.mode:
            raise CandidateEnrichmentStateError("Manual result mode does not match request mode.")
        return self.result
