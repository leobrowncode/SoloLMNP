from datetime import date

from app.domain.loans.posting import (
    choose_posting_path,
    entry_outstanding_allowed,
    funding_before_entry_refused,
)


def test_a_loan_from_before_the_exercise_waits_for_the_property_entry() -> None:
    start = date(2024, 6, 1)
    exercise = date(2025, 1, 1)
    assert (
        choose_posting_path(start_date=start, exercise_start=exercise, property_booked=False)
        == "property_entry"
    )
    assert funding_before_entry_refused(
        start_date=start, exercise_start=exercise, property_booked=False
    )
    assert entry_outstanding_allowed(start_date=start, exercise_start=exercise)


def test_a_loan_that_starts_during_the_exercise_is_drawn_down() -> None:
    start = date(2025, 6, 1)
    exercise = date(2025, 1, 1)
    assert (
        choose_posting_path(start_date=start, exercise_start=exercise, property_booked=False)
        == "funding"
    )
    assert not funding_before_entry_refused(
        start_date=start, exercise_start=exercise, property_booked=False
    )
    assert not entry_outstanding_allowed(start_date=start, exercise_start=exercise)


def test_the_first_day_of_the_exercise_is_a_drawdown() -> None:
    day = date(2025, 1, 1)
    assert (
        choose_posting_path(start_date=day, exercise_start=day, property_booked=False) == "funding"
    )
    assert not entry_outstanding_allowed(start_date=day, exercise_start=day)


def test_after_the_property_entry_the_only_remaining_path_is_the_drawdown() -> None:
    start = date(2024, 6, 1)
    exercise = date(2025, 1, 1)
    assert (
        choose_posting_path(start_date=start, exercise_start=exercise, property_booked=True)
        == "funding"
    )
    assert not funding_before_entry_refused(
        start_date=start, exercise_start=exercise, property_booked=True
    )


def test_without_an_open_exercise_the_path_stays_the_drawdown() -> None:
    assert (
        choose_posting_path(start_date=date(2024, 6, 1), exercise_start=None, property_booked=False)
        == "funding"
    )
