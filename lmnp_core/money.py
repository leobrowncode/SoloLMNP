"""Centimes entiers. Pas de flottant."""

from __future__ import annotations

from decimal import Decimal

from app.core.money import from_cents, to_cents


def cents_to_text(value: int) -> str:
    """Montant signé, deux décimales, point décimal, pour le pont avec la liasse."""
    if type(value) is not int:
        raise TypeError("Les montants du noyau sont des centimes entiers.")
    sign = "-" if value < 0 else ""
    whole, fractional = divmod(abs(value), 100)
    return f"{sign}{whole}.{fractional:02d}"


def text_to_cents(value: str) -> int:
    return to_cents(Decimal(value))


def euros(value: int) -> str:
    """Affichage français : virgule décimale, sans séparateur de milliers."""
    sign = "-" if value < 0 else ""
    whole, fractional = divmod(abs(value), 100)
    return f"{sign}{whole},{fractional:02d}"


__all__ = ["cents_to_text", "euros", "from_cents", "text_to_cents", "to_cents"]
