"""Business dossier status, separate from SQLite readiness.

Inputs are the closing state and the fiscal and export postures already decided
elsewhere. Shipped vintages stay ``research_only``. This status never says
déclarable: a Déclarable trust, when one exists, still stops at « Prêt à
vérifier » or « Clôturé ».
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DOSSIER_INCOMPLET = "incomplet"
DOSSIER_BLOQUE = "bloque"
DOSSIER_PRET_A_VERIFIER = "pret_a_verifier"
DOSSIER_CLOTURE = "cloture"
DOSSIER_STATUSES = (
    DOSSIER_INCOMPLET,
    DOSSIER_BLOQUE,
    DOSSIER_PRET_A_VERIFIER,
    DOSSIER_CLOTURE,
)

DOSSIER_LABELS = {
    DOSSIER_INCOMPLET: "Incomplet",
    DOSSIER_BLOQUE: "Bloqué",
    DOSSIER_PRET_A_VERIFIER: "Prêt à vérifier",
    DOSSIER_CLOTURE: "Clôturé",
}

VINTAGE_STATUS = "research_only"
_YEAR_STATUSES = frozenset({"OPEN", "READY_TO_CLOSE", "CLOSED"})
_KNOWN_TRUSTS = frozenset({"recherche", "provisoire", "declarable"})
_POSTURES = frozenset({"provisoire", "bloquee", "finale"})
_LIASSE_EXPORTS = ("liasse", "pdf")
_CLOSED_EXPORTS = ("liasse", "pdf", "fec", "archive")


def classify_dossier(
    *,
    year_status: str | None,
    output_status: str | None,
    exports: Mapping[str, Any] | None,
    produced: bool,
) -> str:
    """One of incomplet, bloque, pret_a_verifier, cloture.

    ``output_status`` is read so an unknown fiscal trust cannot look ready.
    The value ``declarable`` is a known trust and nothing more: it is not a
    dossier status. Before closing, a blocked FEC is expected and does not
    block the dossier. After closing, a blocked liasse, PDF, FEC or archive does.
    """
    if year_status not in _YEAR_STATUSES:
        return DOSSIER_INCOMPLET
    if year_status == "CLOSED":
        if _blocked(exports, _CLOSED_EXPORTS):
            return DOSSIER_BLOQUE
        return DOSSIER_CLOTURE
    if not produced or output_status not in _KNOWN_TRUSTS:
        return DOSSIER_INCOMPLET
    if _blocked(exports, _LIASSE_EXPORTS):
        return DOSSIER_BLOQUE
    return DOSSIER_PRET_A_VERIFIER


def public_dossier(
    *,
    year_status: str | None,
    output_status: str | None,
    exports: Mapping[str, Any] | None,
    produced: bool,
    fiscal_year_id: int | None,
    year: int | None,
) -> dict[str, Any]:
    """API view. ``vintage_status`` is always research_only. No déclarable label."""
    code = classify_dossier(
        year_status=year_status,
        output_status=output_status,
        exports=exports,
        produced=produced,
    )
    stored_year = year_status if year_status in _YEAR_STATUSES else None
    return {
        "status": code,
        "label": DOSSIER_LABELS[code],
        "fiscal_year_id": fiscal_year_id,
        "year": year,
        "year_status": stored_year,
        "vintage_status": VINTAGE_STATUS,
    }


def _blocked(exports: Mapping[str, Any] | None, kinds: tuple[str, ...]) -> bool:
    return any(_posture(exports, kind) == "bloquee" for kind in kinds)


def _posture(exports: Mapping[str, Any] | None, kind: str) -> str:
    if exports is None:
        return "bloquee"
    slot = exports.get(kind)
    if isinstance(slot, Mapping):
        raw = slot.get("posture")
        if isinstance(raw, str) and raw in _POSTURES:
            return raw
    return "bloquee"
