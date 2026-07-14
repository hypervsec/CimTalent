from app.domain.jobs.exceptions import JobDomainError


class SourcingDomainError(JobDomainError):
    code = "sourcing_error"
    default_message = "A sourcing operation failed."


class JobNotParsedError(SourcingDomainError):
    code = "job_not_parsed"
    default_message = "Job posting must be parsed before queries can be generated."


class JobQueryGenerationStateError(SourcingDomainError):
    code = "job_query_generation_invalid_state"
    default_message = "Queries cannot be generated in the current job state."


class QueryGenerationError(SourcingDomainError):
    code = "query_generation_error"
    default_message = "Search queries could not be generated."


class SearchQueryNotFoundError(SourcingDomainError):
    code = "search_query_not_found"
    default_message = "Search query was not found."


class DuplicateSearchQueryError(SourcingDomainError):
    code = "duplicate_search_query"
    default_message = "A matching search query already exists."


class SearchQueryPersistenceError(SourcingDomainError):
    code = "search_query_persistence_error"
    default_message = "Search query data could not be persisted."


class InvalidTargetDomainError(SourcingDomainError):
    code = "invalid_target_domain"
    default_message = "Target domain is invalid."


class ManualImportValidationError(SourcingDomainError):
    code = "manual_import_validation_error"
    default_message = "Manual search result payload is invalid."


class ManualImportPayloadTooLargeError(SourcingDomainError):
    code = "manual_import_payload_too_large"
    default_message = "Manual search result payload is too large."


class SearchResultParsingError(SourcingDomainError):
    code = "search_result_parsing_error"
    default_message = "Search results could not be parsed."


class SearchResultPersistenceError(SourcingDomainError):
    code = "search_result_persistence_error"
    default_message = "Search results could not be persisted."


class SearchResultNotFoundError(SourcingDomainError):
    code = "search_result_not_found"
    default_message = "Search result was not found."
