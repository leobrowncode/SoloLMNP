"""Exact EUR storage boundary: fractional cents are errors, never rounded."""

from decimal import Decimal, localcontext

MAX_CENTS = 2**63 - 1


def to_cents(value: Decimal) -> int:
    if not isinstance(value, Decimal):
        raise TypeError("Money must be a Decimal")
    if not value.is_finite():
        raise ValueError("Money must be finite")
    if value.copy_abs() > Decimal("92233720368547758.07"):
        raise ValueError("Money exceeds the SQLite integer range")
    digits = value.as_tuple()
    exponent = digits.exponent
    if isinstance(exponent, int) and exponent < -2 and any(digits.digits[exponent + 2 :]):
        raise ValueError("Money must contain whole cents")
    with localcontext() as context:
        context.prec = 40
        cents = value * 100
        if cents != cents.to_integral_value():
            raise ValueError("Money must contain whole cents")
        return int(cents)


def from_cents(value: int) -> Decimal:
    if type(value) is not int:
        raise TypeError("Stored money must be an integer")
    if abs(value) > MAX_CENTS:
        raise ValueError("Stored money exceeds the SQLite integer range")
    with localcontext() as context:
        context.prec = 40
        return Decimal(value).scaleb(-2)
