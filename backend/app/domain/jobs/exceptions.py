from typing import ClassVar


class JobDomainError(Exception):
    code: ClassVar[str] = "job_error"
    default_message: ClassVar[str] = "A job operation failed."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details
        super().__init__(self.message)


class JobNotFoundError(JobDomainError):
    code = "job_not_found"
    default_message = "Job posting was not found."


class JobValidationError(JobDomainError):
    code = "job_validation_error"
    default_message = "Job posting data is invalid."


class InvalidJobStatusTransitionError(JobDomainError):
    code = "invalid_job_status_transition"
    default_message = "The requested job status transition is not allowed."


class DuplicateJobError(JobDomainError):
    code = "duplicate_job"
    default_message = "A matching job posting already exists."


class JobConflictError(JobDomainError):
    code = "job_conflict"
    default_message = "The job operation conflicts with persisted data."


class JobPersistenceError(JobDomainError):
    code = "job_persistence_error"
    default_message = "The job operation could not be persisted."
