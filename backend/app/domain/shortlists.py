from app.db.enums import ShortlistStatus
from app.domain.jobs.exceptions import JobConflictError, JobNotFoundError


class ShortlistNotFoundError(JobNotFoundError):
    code = "shortlist_not_found"
    default_message = "Shortlist entry was not found."


class InvalidShortlistStatusTransitionError(JobConflictError):
    code = "invalid_shortlist_status_transition"
    default_message = "The requested shortlist status transition is not allowed."


ALLOWED_TRANSITIONS = {
    ShortlistStatus.SHORTLISTED: {
        ShortlistStatus.REVIEWED,
        ShortlistStatus.REJECTED,
        ShortlistStatus.CONTACTED,
    },
    ShortlistStatus.REVIEWED: {
        ShortlistStatus.SHORTLISTED,
        ShortlistStatus.REJECTED,
        ShortlistStatus.CONTACTED,
    },
    ShortlistStatus.CONTACTED: {ShortlistStatus.REVIEWED, ShortlistStatus.REJECTED},
    ShortlistStatus.REJECTED: {ShortlistStatus.SHORTLISTED, ShortlistStatus.REVIEWED},
}
