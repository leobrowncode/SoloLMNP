"""Contrôle SIRET (clé de Luhn sur les 14 chiffres)."""

from __future__ import annotations


def valide(siret: str) -> bool:
    if len(siret) != 14 or not siret.isdigit():
        return False
    digits = [int(char) for char in siret]
    total = 0
    double = False
    for value in reversed(digits):
        scaled = value * 2 if double else value
        if scaled > 9:
            scaled -= 9
        total += scaled
        double = not double
    return total % 10 == 0
