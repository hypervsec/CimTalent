from typing import ClassVar


class CandidateDomainError(Exception):
    code: ClassVar[str] = "candidate_error"
    default_message: ClassVar[str] = "A candidate operation failed."

    def __init__(
        self, message: str | None = None, *, details: dict[str, object] | None = None
    ) -> None:
        self.message = message or self.default_message
        self.details = details
        super().__init__(self.message)


class CandidateNotFoundError(CandidateDomainError):
    code = "candidate_not_found"
    default_message = "Candidate was not found."


class CandidateValidationError(CandidateDomainError):
    code = "candidate_validation_error"
    default_message = "Candidate data is invalid."


class DuplicateCandidateError(CandidateDomainError):
    code = "duplicate_candidate"
    default_message = "A candidate with the same profile URL already exists."


class CandidateDiscoveryError(CandidateDomainError):
    code = "candidate_discovery_error"
    default_message = "Candidate discovery failed."


class SearchResultNotEligibleError(CandidateDomainError):
    code = "search_result_not_eligible"
    default_message = "Search result is not eligible for candidate discovery."


class CandidateAlreadyLinkedError(CandidateDomainError):
    code = "candidate_already_linked"
    default_message = "Search result is already linked to a candidate."


class CandidateMergeError(CandidateDomainError):
    code = "candidate_merge_error"
    default_message = "Candidates could not be merged."


class CandidateMergeConflictError(CandidateDomainError):
    code = "candidate_merge_conflict"
    default_message = "Candidate merge has an unresolved conflict."


class InvalidCandidateStatusTransitionError(CandidateDomainError):
    code = "invalid_candidate_status_transition"
    default_message = "The requested candidate status transition is not allowed."


class CandidatePersistenceError(CandidateDomainError):
    code = "candidate_persistence_error"
    default_message = "The candidate operation could not be persisted."


class CandidateDeleteConflictError(CandidateDomainError):
    code = "candidate_delete_conflict"
    default_message = "Candidate could not be deleted."


class CandidateMergeAuditError(CandidateDomainError):
    code = "candidate_merge_audit_error"
    default_message = "Candidate merge audit could not be persisted."
