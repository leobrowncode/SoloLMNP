"""Which action may put a registered loan on account 164.

The ledger balance stays the only accounting figure. Contract amounts
(borrowed principal, schedule) are not a balance, even when both are zero.
"""

from datetime import date
from typing import Literal

PostingPath = Literal["property_entry", "funding"]


def choose_posting_path(
    *,
    start_date: date,
    exercise_start: date | None,
    property_booked: bool,
) -> PostingPath:
    """One path onto the balance sheet.

    A loan that already existed when the exercise opened is taken up by the
    property entry (capital restant dû). A loan that starts during the exercise
    is drawn down. Once the property entry is posted it cannot be repeated, so
    a loan still off the books uses the drawdown.
    """
    if property_booked or exercise_start is None or start_date >= exercise_start:
        return "funding"
    return "property_entry"


def funding_before_entry_refused(
    *,
    start_date: date,
    exercise_start: date,
    property_booked: bool,
) -> bool:
    """A pre-existing loan is not drawn down while the property entry is still open."""
    return start_date < exercise_start and not property_booked


def entry_outstanding_allowed(*, start_date: date, exercise_start: date) -> bool:
    """Only a loan that predates the exercise is capital restant dû at entry."""
    return start_date < exercise_start
