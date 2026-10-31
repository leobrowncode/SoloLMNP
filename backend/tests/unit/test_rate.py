from decimal import Decimal

import pytest

from app.core.rate import format_rate, to_rate_millis


def test_three_decimals_round_trip() -> None:
    assert to_rate_millis(Decimal("3.50")) == 3500
    assert to_rate_millis(Decimal("3.125")) == 3125
    assert format_rate(3500) == "3.50"
    assert format_rate(3125) == "3.125"
    assert format_rate(0) == "0.00"


@pytest.mark.parametrize("value", ["3.1251", "100.001", "-0.001", "NaN"])
def test_rate_rejects_a_fourth_decimal_and_out_of_range(value: str) -> None:
    with pytest.raises(ValueError):
        to_rate_millis(Decimal(value))
