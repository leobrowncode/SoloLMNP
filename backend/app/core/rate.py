"""Annual interest rate stored as thousandths of a percent.

3.50 % is 3500. 3.125 % is 3125. The loan column keeps the historical name
``interest_rate_basis_points``. Migration 0012 multiplies values already
stored at the old hundredths-of-a-percent scale by 10.
"""

from decimal import Decimal, localcontext

MAX_RATE_MILLIS = 100_000


def parse_rate(value: object) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("Le taux doit être une chaîne décimale, par exemple 3.125.")
    try:
        rate = Decimal(value)
        to_rate_millis(rate)
    except (ArithmeticError, ValueError) as exc:
        raise ValueError("Taux annuel entre 0 et 100, au plus trois décimales.") from exc
    return rate


def parse_optional_rate(value: object) -> Decimal | None:
    if value is None:
        return None
    return parse_rate(value)


def to_rate_millis(value: Decimal) -> int:
    if not isinstance(value, Decimal):
        raise TypeError("A rate must be a Decimal")
    if not value.is_finite():
        raise ValueError("Un taux doit être fini.")
    if value < 0 or value > Decimal(100):
        raise ValueError("Le taux annuel doit être compris entre 0 et 100.")
    digits = value.as_tuple()
    exponent = digits.exponent
    if isinstance(exponent, int) and exponent < -3 and any(digits.digits[exponent + 3 :]):
        raise ValueError("Le taux accepte au plus trois décimales.")
    with localcontext() as context:
        context.prec = 40
        millis = value * 1000
        if millis != millis.to_integral_value():
            raise ValueError("Le taux accepte au plus trois décimales.")
        stored = int(millis)
    if stored > MAX_RATE_MILLIS:
        raise ValueError("Le taux annuel doit être compris entre 0 et 100.")
    return stored


def format_rate(millis: int) -> str:
    """API decimal. 3500 stays ``3.50``; 3125 is ``3.125``."""
    if type(millis) is not int:
        raise TypeError("A stored rate must be an integer")
    if millis < 0:
        raise ValueError("Un taux stocké ne peut pas être négatif.")
    whole, fraction = divmod(millis, 1000)
    text = f"{fraction:03d}".rstrip("0")
    if len(text) < 2:
        text = text.ljust(2, "0")
    return f"{whole}.{text}"
