class EnrichmentDomainError(Exception):
    code = "enrichment_error"

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class CandidateEnrichmentValidationError(EnrichmentDomainError):
    code = "candidate_enrichment_validation_error"


class CandidateEnrichmentStateError(EnrichmentDomainError):
    code = "candidate_enrichment_state_error"


class CandidateEnrichmentPersistenceError(EnrichmentDomainError):
    code = "candidate_enrichment_persistence_error"


class EnrichmentRunNotFoundError(EnrichmentDomainError):
    code = "enrichment_run_not_found"


class UnsupportedEnrichmentProviderError(EnrichmentDomainError):
    code = "unsupported_enrichment_provider"


class EnrichmentPayloadTooLargeError(EnrichmentDomainError):
    code = "enrichment_payload_too_large"


class EnrichmentConflictError(EnrichmentDomainError):
    code = "enrichment_conflict"


class EnrichmentNormalizationError(EnrichmentDomainError):
    code = "enrichment_normalization_error"


class InvalidEnrichmentStatusTransitionError(EnrichmentDomainError):
    code = "invalid_enrichment_status_transition"
