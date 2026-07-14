from app.db.enums import ShortlistStatus
from app.domain.shortlists import ALLOWED_TRANSITIONS
from app.services.shortlists import ShortlistService


def test_shortlist_transition_matrix_allows_expected_changes() -> None:
    assert ShortlistStatus.CONTACTED in ALLOWED_TRANSITIONS[ShortlistStatus.SHORTLISTED]
    assert ShortlistStatus.SHORTLISTED in ALLOWED_TRANSITIONS[ShortlistStatus.REJECTED]
    assert ShortlistStatus.CONTACTED not in ALLOWED_TRANSITIONS[ShortlistStatus.CONTACTED]


def test_csv_formula_values_are_escaped() -> None:
    assert ShortlistService._safe("=SUM(A1:A2)") == "'=SUM(A1:A2)"
    assert ShortlistService._safe("İstanbul") == "İstanbul"
