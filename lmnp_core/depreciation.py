"""Amortissement linéaire en jours réels.

Même formule que ``calculate_year`` dans ``app.services.assets`` : cumul arrondi
moitié vers le haut, dotation = écart de cumuls. ``add_months`` est la même
fonction. Le test d'alignement verrouille les deux copies.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

# Grille de ``DWELLING_PARTS`` : quote-part en dix-millièmes, durée en mois, comptes.
# Ce n'est pas un barème légal. Un dossier peut fournir ses propres composants.
COMPOSANTS_DEFAUT = (
    ("gros_oeuvre", "Gros oeuvre", 4000, 480, "213000", "281300"),
    ("toiture", "Toiture et etancheite", 1000, 300, "213500", "281350"),
    ("facade", "Facade et menuiseries", 1000, 240, "213500", "281350"),
    ("electricite", "Installations electriques", 1000, 240, "213500", "281350"),
    ("plomberie", "Plomberie et sanitaires", 1000, 240, "213500", "281350"),
    ("agencements", "Agencements interieurs", 2000, 180, "213500", "281350"),
)


def add_months(value: date, months: int) -> date:
    index = value.month - 1 + months
    year, month = value.year + index // 12, index % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def shares(base: int) -> list[int]:
    """Même répartition que ``_component_shares`` : reliquat sur le dernier poste."""
    if type(base) is not int or base < 0:
        raise ValueError("La base amortissable est un nombre de centimes.")
    ratios = [part[2] for part in COMPOSANTS_DEFAUT]
    parts = [base * ratio // 10000 for ratio in ratios]
    parts[-1] += base - sum(parts)
    for index, part in enumerate(parts):
        if part < 0:
            parts[0] += part
            parts[index] = 0
    return parts


@dataclass(frozen=True)
class Plan:
    cle: str
    libelle: str
    base: int
    duree_mois: int
    compte: str
    compte_amortissement: str
    mise_en_service: date

    @property
    def fin(self) -> date:
        return add_months(self.mise_en_service, self.duree_mois) - timedelta(days=1)


def dotation(plan: Plan, debut: date, fin: date) -> int:
    """Dotation de la fenêtre [debut, fin], en centimes. 0 si la fenêtre est vide."""
    start = max(debut, plan.mise_en_service)
    end = min(fin, plan.fin)
    if start > end:
        return 0
    total_days = (plan.fin - plan.mise_en_service).days + 1
    before_days = max(0, (start - plan.mise_en_service).days)
    end_days = min(total_days, (end - plan.mise_en_service).days + 1)
    base = Decimal(plan.base)
    cumulative_before = int(
        (base * Decimal(before_days) / Decimal(total_days)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )
    accumulated = int(
        (base * Decimal(end_days) / Decimal(total_days)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )
    return accumulated - cumulative_before
