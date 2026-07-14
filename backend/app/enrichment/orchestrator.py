from app.domain.enrichment.types import (
    CandidateEnrichmentProvider,
    CandidateEnrichmentRequest,
    CandidateEnrichmentResult,
)


class CandidateEnrichmentOrchestrator:
    def __init__(self, provider: CandidateEnrichmentProvider) -> None:
        self.provider = provider

    async def run(self, request: CandidateEnrichmentRequest) -> CandidateEnrichmentResult:
        return await self.provider.enrich(request)
