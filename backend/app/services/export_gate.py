"""Gate liasse and filing downloads on the posture already stored on each export."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.api_errors import RESOLUTION_ACTIONS
from app.domain.filing.fec import render_fec
from app.domain.fiscal.output_status import (
    align_controlled_exports,
    classify,
    download_refusal,
    load_validation,
)
from app.services.efi import efi_worksheet
from app.services.ledger import fail, get_year

_FEC_EXPORTS = frozenset({"fec", "archive"})
_LIASSE_FALLBACK = {
    "label": "Voir la liasse",
    "href": "/fiscalite#sorties-figees",
}


def export_status(session: Session, year_id: int) -> dict[str, Any]:
    """Posture of each output, including before a fiscal calculation exists."""
    year = get_year(session, year_id)
    siren_ok, fec_errors = _fec_facts(session, year_id)
    sheet = _worksheet(session, year_id)
    if sheet is None:
        summary = classify(
            validation=load_validation(year.fiscal_vintage),
            copy_complete=False,
            year_closed=year.status == "CLOSED",
            produced=False,
            fec_blocked=bool(fec_errors) or not siren_ok,
        )
        exports = summary["exports"]
        output_status = str(summary["output_status"])
        output_label = str(summary["output_label"])
        blocking: list[dict[str, str]] = []
        produced = False
    else:
        exports = sheet.get("exports") or {}
        output_status = str(sheet.get("output_status") or "recherche")
        output_label = str(sheet.get("output_label") or "Recherche")
        blocking = _notices(sheet.get("blocking"))
        produced = True
    exports = align_controlled_exports(
        exports if isinstance(exports, dict) else {},
        year_closed=year.status == "CLOSED",
        fec_blocked=bool(fec_errors) or not siren_ok,
    )
    return {
        "fiscal_year_id": year.id,
        "year_status": year.status,
        "output_status": output_status,
        "output_label": output_label,
        "produced": produced,
        "exports": exports,
        "prerequisites": _prerequisites(
            produced=produced,
            year_closed=year.status == "CLOSED",
            siren_ok=siren_ok,
            fec_errors=fec_errors,
            blocking=blocking,
            exports=exports,
        ),
    }


def require_export(session: Session, year_id: int, kind: str) -> dict[str, Any]:
    """Refuse a Bloquée download with the structured error. Return the status otherwise."""
    status = export_status(session, year_id)
    refusal = download_refusal(kind, status)
    if refusal is None:
        return status
    fail(
        str(refusal["code"]),
        str(refusal["message"]),
        action=_action(refusal.get("action")),
        issues=_issues(refusal.get("issues")),
    )


def _worksheet(session: Session, year_id: int) -> dict[str, Any] | None:
    try:
        return efi_worksheet(session, year_id)
    except HTTPException as exc:
        detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
        if detail.get("code") == "FISCAL_NOT_COMPUTED":
            return None
        raise


def _fec_facts(session: Session, year_id: int) -> tuple[bool, list[dict[str, str]]]:
    rendered = render_fec(session, year_id)
    return bool(rendered["siren"]), _notices(rendered["validation"]["errors"])


def _prerequisites(
    *,
    produced: bool,
    year_closed: bool,
    siren_ok: bool,
    fec_errors: list[dict[str, str]],
    blocking: list[dict[str, str]],
    exports: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not _downloadable(exports, "pdf"):
        if not produced:
            items.append(
                _item(
                    "FISCAL_NOT_COMPUTED",
                    "Calculez le résultat fiscal avant de télécharger la liasse ou le PDF.",
                    "liasse",
                )
            )
        elif blocking:
            items.extend(_item(row["code"], row["message"], "liasse") for row in blocking)
        else:
            items.append(
                _item(
                    "EXPORT_BLOCKED",
                    "La liasse n’est pas téléchargeable tant que les contrôles de cases "
                    "ne sont pas satisfaits.",
                    "liasse",
                )
            )
    if not _downloadable(exports, "fec"):
        if not year_closed:
            items.append(
                _item(
                    "YEAR_NOT_CLOSED",
                    "Le FEC final et le dossier de contrôle exigent un exercice clôturé.",
                    "fec",
                )
            )
        elif not siren_ok:
            items.append(
                _item(
                    "SIREN_REQUIRED",
                    "Le nom du FEC commence par le SIREN. "
                    "Indiquez-le dans Comptabilité → Identité.",
                    "fec",
                )
            )
        elif fec_errors:
            items.extend(_item("FEC_INVALID", row["message"], "fec") for row in fec_errors)
        else:
            liasse_reasons = [row for row in items if row["export"] == "liasse"]
            if liasse_reasons:
                items.extend(_item(row["code"], row["message"], "fec") for row in liasse_reasons)
            else:
                items.append(
                    _item(
                        "EXPORT_BLOCKED",
                        "Le FEC suit la liasse. Il reste bloqué tant que la liasse l’est.",
                        "fec",
                    )
                )
    return items


def _downloadable(exports: dict[str, Any], kind: str) -> bool:
    slot = exports.get(kind)
    return isinstance(slot, dict) and slot.get("download") is True


def _item(code: str, message: str, export: str) -> dict[str, Any]:
    family = "fec" if export in _FEC_EXPORTS else "liasse"
    action = RESOLUTION_ACTIONS.get(code)
    if action is None:
        action = _LIASSE_FALLBACK if family == "liasse" else RESOLUTION_ACTIONS["EXPORT_BLOCKED"]
    return {"code": code, "message": message, "export": export, "action": dict(action)}


def _action(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    label = value.get("label")
    href = value.get("href")
    if isinstance(label, str) and isinstance(href, str):
        return {"label": label, "href": href}
    return None


def _issues(value: object) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    issues = [item for item in value if isinstance(item, dict)]
    return issues or None


def _notices(items: object) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    notices: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        message = item.get("message")
        if isinstance(code, str) and isinstance(message, str):
            notices.append({"code": code, "message": message})
    return notices
