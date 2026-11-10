"""État de suivi des amortissements non déduits (article 39 C)."""

from __future__ import annotations

from lmnp_core.build import Annee
from lmnp_core.money import euros


def etat(annees: list[Annee]) -> dict[str, object]:
    """FIFO par année d'origine, même ordre que le moteur fiscal."""
    stocks: dict[int, int] = {}
    lignes: list[dict[str, object]] = []
    for item in annees:
        a_imputer = item.amortissement_anterieur_utilise
        for origin in sorted(stocks):
            take = min(stocks[origin], a_imputer)
            if take:
                stocks[origin] -= take
                a_imputer -= take
                lignes.append(_ligne(item.annee, origin, "impute", take))
        if item.non_deduit:
            stocks[item.annee] = stocks.get(item.annee, 0) + item.non_deduit
            lignes.append(_ligne(item.annee, item.annee, "non_deduit", item.non_deduit))
        stocks = {origin: left for origin, left in stocks.items() if left}
    return {
        "titre": "Etat de suivi des amortissements non deduits (article 39 C)",
        "lignes": lignes,
        "stock_fin": [
            {"origine": origin, "restant_centimes": left, "restant": euros(left)}
            for origin, left in sorted(stocks.items())
        ],
    }


def lignes_texte(suivi: dict[str, object]) -> list[str]:
    lines = [str(suivi["titre"]), "Le stock 39 C ne se perime pas."]
    for row in _dicts(suivi["lignes"]):
        lines.append(
            f"{row['exercice']} origine {row['origine']} {row['mouvement']} {row['montant']}"
        )
    for row in _dicts(suivi["stock_fin"]):
        lines.append(f"Stock fin origine {row['origine']} {row['restant']}")
    if not suivi["stock_fin"]:
        lines.append("Stock fin : 0")
    return lines


def _dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise TypeError("Suivi illisible.")
    return [item for item in value if isinstance(item, dict)]


def _ligne(exercice: int, origin: int, mouvement: str, cents: int) -> dict[str, object]:
    return {
        "exercice": exercice,
        "origine": origin,
        "mouvement": mouvement,
        "centimes": cents,
        "montant": euros(cents),
    }
