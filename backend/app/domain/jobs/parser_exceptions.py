from app.domain.jobs.exceptions import JobDomainError


class JobParseStateError(JobDomainError):
    code = "job_parse_invalid_state"
    default_message = "Job posting cannot be parsed in its current state."


class JobParsingError(JobDomainError):
    code = "job_parsing_error"
    default_message = "Job posting could not be parsed."


class EmptyJobDescriptionError(JobDomainError):
    code = "empty_job_description"
    default_message = "Job description cannot be empty."


class RequirementPersistenceError(JobDomainError):
    code = "requirement_persistence_error"
    default_message = "Parsed requirements could not be persisted."
