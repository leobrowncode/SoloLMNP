"""Close and reopen a fiscal year. Snapshots are superseded, never deleted."""

import hashlib
import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.filing.fec import render_fec
from app.domain.filing.mappings import compile_package
from app.models import AccountingEntry, FiscalYear
from app.models.assets import DepreciationPeriod
from app.models.base import utc_now
from app.models.filing import AuditEvent, TaxReturnSnapshot
from app.models.fiscal import FiscalComputation
from app.services.fiscal import latest_fiscal, ledger_fingerprint
from app.services.ledger import fail, get_year
from app.services.result_closing import _live
from app.services.statements import statements


def precheck(session: Session, year_id: int) -> dict[str, Any]:
    year = get_year(session, year_id)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    drafts = session.scalar(
        select(func.count())
        .select_from(AccountingEntry)
        .where(AccountingEntry.fiscal_year_id == year.id, AccountingEntry.status == "DRAFT")
    )
    if drafts:
        errors.append({"code": "YEAR_DRAFTS", "message": "Des brouillons sont encore ouverts."})
    report = _capture(lambda: statements(session, year.id), errors, "STATEMENTS")
    if (
        report is not None
        and _open_classes(report)
        and _live(session, year.id, "CENTRALIZATION") is None
    ):
        errors.append(
            {"code": "CENTRALIZATION_REQUIRED", "message": "Centralisez les charges et produits."}
        )
    pending = session.scalar(
        select(func.count())
        .select_from(DepreciationPeriod)
        .where(
            DepreciationPeriod.fiscal_year_id == year.id,
            DepreciationPeriod.status == "CALCULATED",
        )
    )
    if pending:
        errors.append(
            {
                "code": "DEPRECIATION_UNPOSTED",
                "message": "Des dotations calculées ne sont pas comptabilisées.",
            }
        )
    fiscal = _capture(lambda: latest_fiscal(session, year.id), errors, "FISCAL_NOT_COMPUTED")
    if fiscal is not None and fiscal["ledger_sha256"] != ledger_fingerprint(session, year.id):
        errors.append(
            {"code": "FISCAL_STALE", "message": "Le calcul fiscal ne correspond plus au ledger."}
        )
    elif fiscal is not None:
        warnings.append(
            {
                "code": "FISCAL_RESEARCH",
                "message": "Le calcul fiscal reste en recherche et n’est pas déclarable.",
            }
        )
    fec = render_fec(session, year.id)
    errors.extend(fec["validation"]["errors"])
    package = _capture(lambda: compile_package(session, year.id), errors, "MAPPING")
    if package is not None:
        errors.extend(package["errors"])
        warnings.extend(package["warnings"])
    return {
        "fiscal_year_id": year.id,
        "year_status": year.status,
        "errors": errors,
        "warnings": warnings,
        "infos": [
            {
                "code": "FEC_SCOPE",
                "message": (
                    "Le FEC exclut les écritures de centralisation "
                    "et ne lit que les lignes validées."
                ),
            },
            {
                "code": "FISCAL_SCOPE",
                "message": (
                    "Liasse de l’exercice à recopier sur impots.gouv.fr. "
                    "LMP, cession, TVA et plus-values restent hors de cette feuille."
                ),
            },
        ],
        "blocking": bool(errors),
    }


def mark_ready(session: Session, year_id: int, acknowledged: list[str]) -> dict[str, Any]:
    year = get_year(session, year_id)
    if year.status == "CLOSED":
        fail("YEAR_CLOSED", "L’exercice est déjà clôturé.")
    report = precheck(session, year_id)
    if report["blocking"]:
        fail("CLOSE_BLOCKED", "Le pré-contrôle contient des erreurs.")
    expected = {item["code"] for item in report["warnings"]}
    if set(acknowledged) != expected:
        fail("WARNINGS_UNACKNOWLEDGED", "Tous les avertissements doivent être accusés.")
    before = year.status
    year.status = "READY_TO_CLOSE"
    _audit(session, year, "READY_TO_CLOSE", before, year.status, "")
    return precheck(session, year_id)


def close_year(session: Session, year_id: int, confirmation: str) -> dict[str, Any]:
    if confirmation != "CLOTURER":
        fail("CONFIRMATION_REQUIRED", "Confirmez la clôture avec le libellé demandé.", 422)
    year = get_year(session, year_id)
    if year.status != "READY_TO_CLOSE":
        fail("NOT_READY", "Passez l’exercice en prêt à clôturer avant de le figer.")
    report = precheck(session, year_id)
    if report["blocking"]:
        fail("CLOSE_BLOCKED", "Le pré-contrôle contient des erreurs.")
    before = year.status
    year.status = "CLOSED"
    year.closed_at = utc_now()
    package = compile_package(session, year.id)
    _supersede(session, year.id)
    generation = (
        session.scalar(
            select(func.max(TaxReturnSnapshot.generation)).where(
                TaxReturnSnapshot.fiscal_year_id == year.id
            )
        )
        or 0
    ) + 1
    canonical = json.dumps(package, sort_keys=True, ensure_ascii=False)
    session.add(
        TaxReturnSnapshot(
            fiscal_year_id=year.id,
            generation=generation,
            status="CURRENT",
            canonical_json=canonical,
            sha256=hashlib.sha256(canonical.encode()).hexdigest(),
            ledger_sha256=package["ledger_sha256"],
        )
    )
    _audit(session, year, "CLOSED", before, "CLOSED", "")
    session.flush()
    return {"fiscal_year_id": year.id, "status": year.status, "generation": generation}


def reopen_year(session: Session, year_id: int, confirmation: str, reason: str) -> dict[str, Any]:
    if confirmation != "ROUVRIR":
        fail("CONFIRMATION_REQUIRED", "Confirmez la réouverture avec le libellé demandé.", 422)
    year = get_year(session, year_id)
    if year.status != "CLOSED":
        fail("YEAR_NOT_CLOSED", "Seul un exercice clôturé peut être rouvert.")
    before = year.status
    year.status = "OPEN"
    year.closed_at = None
    year.reopened_at = utc_now()
    year.reopening_reason = reason
    _supersede(session, year.id)
    for row in session.scalars(
        select(FiscalComputation).where(
            FiscalComputation.fiscal_year_id == year.id,
            FiscalComputation.invalidated_at.is_(None),
        )
    ):
        row.invalidated_at = utc_now()
    _audit(session, year, "REOPENED", before, "OPEN", reason)
    session.flush()
    return {"fiscal_year_id": year.id, "status": year.status}


def _open_classes(report: dict[str, Any]) -> bool:
    rows = report["income_statement"]["income"] + report["income_statement"]["expenses"]
    return any(row["amount"] not in {"0.00", "-0.00"} for row in rows)


def _capture(callback: Any, errors: list[dict[str, str]], code: str) -> Any:
    try:
        return callback()
    except HTTPException as exc:
        detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
        errors.append(
            {"code": str(detail.get("code", code)), "message": str(detail.get("message", code))}
        )
        return None


def _supersede(session: Session, year_id: int) -> None:
    for row in session.scalars(
        select(TaxReturnSnapshot).where(
            TaxReturnSnapshot.fiscal_year_id == year_id,
            TaxReturnSnapshot.status == "CURRENT",
        )
    ):
        row.status = "SUPERSEDED"


def _audit(
    session: Session, year: FiscalYear, action: str, before: str, after: str, reason: str
) -> None:
    session.add(
        AuditEvent(
            entity="fiscal_year",
            entity_id=str(year.id),
            action=action,
            before={"status": before},
            after={"status": after},
            reason=reason,
            metadata_json={},
        )
    )
    session.flush()
