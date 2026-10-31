"""Register gross versus the validated ledger.

Amounts are integer cents. A missing gross before the exercise points to the
property entry. A purchase during the exercise points to a journal entry.
Nothing here guesses a fiscal treatment.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

Fix = Literal["ok", "entry", "journal"]

ENTRY_CODE = "ASSET_NOT_BOOKED"
JOURNAL_CODE = "ASSET_PURCHASE_UNBOOKED"
ECART_CODE = "IMMOBILISATIONS_ECART"
NET_CODE = "IMMOBILISATIONS_NETTES_NEGATIVES"

ENTRY_MESSAGE = (
    "Le bien n’est pas entré en comptabilité : le brut du registre n’est pas au journal. "
    "Faites entrer le bien avant de comptabiliser les dotations."
)
JOURNAL_MESSAGE = (
    "L’immobilisation acquise pendant l’exercice n’est pas au journal. "
    "Inscrivez son brut au compte d’immobilisation avant de comptabiliser la dotation."
)
ECART_MESSAGE = (
    "Le registre des immobilisations ne retrouve pas les comptes 21, 28 et 681. "
    "Faites entrer le bien en comptabilité. Cet écart bloque la clôture "
    "et ne peut pas être accusé."
)
NET_MESSAGE = (
    "La case 030 du 2033-A (immobilisations corporelles nettes) est négative. "
    "Inscrivez le bien au bilan avant de clôturer : les amortissements "
    "dépassent le brut comptabilisé."
)

ENTRY_ACTION = {
    "label": "Faire entrer le bien en comptabilité",
    "href": "/immobilisations#entree-bien",
}
JOURNAL_ACTION = {
    "label": "Inscrire l’immobilisation au journal",
    "href": "/comptabilite/brouillons#nouvelle-ecriture",
}


@dataclass(frozen=True, slots=True)
class RegisterPiece:
    account: str
    cents: int
    acquired: date


def registration_gap(
    pieces: list[RegisterPiece],
    ledger: Mapping[str, int],
    *,
    as_of: date,
    year_start: date,
    accounts: Collection[str] | None = None,
) -> tuple[dict[str, int], Fix]:
    """Shortfall of register gross against validated ledger balances.

    ``ledger`` values are debit-positive cents. ``accounts`` limits the check
    to one immobilisation; the register total of a shared account still applies.
    """
    active = [piece for piece in pieces if piece.cents > 0 and piece.acquired <= as_of]
    register: dict[str, int] = {}
    for piece in active:
        _cents(piece.cents)
        register[piece.account] = register.get(piece.account, 0) + piece.cents
    scope = set(register) if accounts is None else set(accounts)
    short: dict[str, int] = {}
    for account in scope:
        needed = register.get(account, 0)
        have = _cents(ledger.get(account, 0))
        if have < needed:
            short[account] = needed - have
    if not short:
        return {}, "ok"
    covers_opening = any(
        piece.account in short and piece.acquired <= year_start for piece in active
    )
    return short, "entry" if covers_opening else "journal"


def posting_refusal(fix: Fix) -> dict[str, object]:
    """API refusal for a depreciation that would book amortissement without gross."""
    if fix == "entry":
        return {"code": ENTRY_CODE, "message": ENTRY_MESSAGE, "action": dict(ENTRY_ACTION)}
    if fix == "journal":
        return {"code": JOURNAL_CODE, "message": JOURNAL_MESSAGE, "action": dict(JOURNAL_ACTION)}
    raise ValueError("Aucune immobilisation ne manque au journal.")


def gap_error(
    register_end: tuple[int, int, int], ledger_end: tuple[int, int, int]
) -> dict[str, str] | None:
    """Blocking pre-check when the register and accounts 21, 28 and 681 diverge."""
    if register_end == ledger_end:
        return None
    return {"code": ECART_CODE, "message": ECART_MESSAGE}


def negative_net_error(net_cents: int) -> dict[str, str] | None:
    """Blocking pre-check when 2033-A box 030 would be negative."""
    if _cents(net_cents) >= 0:
        return None
    return {"code": NET_CODE, "message": NET_MESSAGE}


def _cents(value: int) -> int:
    if type(value) is not int:
        raise TypeError("Les montants d’immobilisation sont des centimes entiers.")
    return value
