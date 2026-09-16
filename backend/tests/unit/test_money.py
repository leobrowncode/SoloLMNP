from decimal import Decimal, localcontext

import pytest

from app.core.money import MAX_CENTS, from_cents, to_cents


@pytest.mark.parametrize("cents", [0, 1, -1, 101, -12345678, MAX_CENTS, -MAX_CENTS])
def test_exact_roundtrip_independent_of_decimal_context(cents: int) -> None:
    with localcontext() as context:
        context.prec = 3
        assert to_cents(from_cents(cents)) == cents


@pytest.mark.parametrize(
    "value",
    [
        "NaN",
        "sNaN",
        "Infinity",
        "-Infinity",
        "0.001",
        "-0.001",
        "92233720368547758.08",
        "1e99999",
        "1.00000000000000000000000000000000000000001",
        "-1.00000000000000000000000000000000000000001",
    ],
)
def test_invalid_decimal_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        to_cents(Decimal(value))


@pytest.mark.parametrize("value", [1.2, 1, True, "1.00", None])
def test_non_decimal_rejected(value: object) -> None:
    with pytest.raises(TypeError):
        to_cents(value)  # type: ignore[arg-type]
