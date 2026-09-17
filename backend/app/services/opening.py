"""Read-only preparation of opening balances, before result allocation."""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, AccountingEntry, FiscalYear
from app.services.ledger import fail, get_year, money
from app.services.statements import statements


def _report_cents(amount: str) -> int:
    """Parse internal money() output without imposing a per-line storage limit."""
    return int(amount.replace(".", ""))


def opening_preview(session: Session, year_id: int) -> dict[str, Any]:
    target = get_year(session, year_id)
    previous = session.scalar(
        select(FiscalYear).where(
            FiscalYear.rental_activity_id == target.rental_activity_id,
            FiscalYear.end_date == target.start_date - timedelta(days=1),
        )
    )
    if previous is None:
        fail("PREVIOUS_YEAR_REQUIRED", "Aucun exercice ne se termine la veille de cet exercice.")
    assert previous is not None  # noqa: S101
    report = statements(session, previous.id)
    balance = report["balance_sheet"]
    lines: list[dict[str, Any]] = []
    inactive: list[str] = []
    for group in ("assets", "liabilities", "equity"):
        for row in balance[group]:
            net = _report_cents(row["amount"]) * (1 if group == "assets" else -1)
            if not net:
                continue
            account = session.get(Account, row["account_number"])
            assert account is not None  # noqa: S101
            if not account.active:
                inactive.append(account.number)
            lines.append(
                {
                    "account_number": account.number,
                    "label": row["label"],
                    "debit": money(max(net, 0)),
                    "credit": money(max(-net, 0)),
                }
            )
    lines.sort(key=lambda row: row["account_number"])
    result = _report_cents(report["income_statement"]["result"])
    # Keep the result distinct: this preview neither chooses an allocation account
    # nor creates a class 6/7 balance in the target year (PCG 112-2 and 112-3).
    result_line = {
        "account_number": None,
        "label": "Résultat précédent — compte de reprise à déterminer",
        "debit": money(max(-result, 0)),
        "credit": money(max(result, 0)),
    }
    total_debit = sum(_report_cents(row["debit"]) for row in lines) + max(-result, 0)
    total_credit = sum(_report_cents(row["credit"]) for row in lines) + max(result, 0)
    if total_debit != total_credit:
        fail("UNBALANCED_OPENING", "La prévisualisation des à-nouveaux est déséquilibrée.")
    target_entries = session.scalar(
        select(func.count())
        .select_from(AccountingEntry)
        .where(AccountingEntry.fiscal_year_id == target.id)
    )
    warnings = [
        {
            "code": "PREVIEW_ONLY",
            "message": "Prévisualisation uniquement : aucune écriture créée "
            "et aucune continuité certifiée.",
        }
    ]
    if previous.status != "CLOSED":
        warnings.append(
            {
                "code": "SOURCE_NOT_CLOSED",
                "message": "L’exercice précédent n’est pas clôturé : ces soldes peuvent changer.",
            }
        )
    if report["excluded_draft_count"]:
        warnings.append(
            {
                "code": "SOURCE_DRAFTS",
                "message": "Des brouillons de l’exercice précédent sont exclus des montants.",
            }
        )
    if target.status != "OPEN":
        warnings.append(
            {
                "code": "TARGET_NOT_OPEN",
                "message": "L’exercice destinataire n’est pas ouvert à la saisie.",
            }
        )
    if target_entries:
        warnings.append(
            {
                "code": "TARGET_HAS_ENTRIES",
                "message": "L’exercice destinataire contient déjà des écritures : "
                "vérifier les reprises existantes avant toute génération.",
            }
        )
    if inactive:
        warnings.append(
            {
                "code": "INACTIVE_ACCOUNTS",
                "message": "Des soldes concernent des comptes inactifs : "
                + ", ".join(sorted(inactive))
                + ".",
            }
        )
    if result:
        warnings.append(
            {
                "code": "RESULT_ACCOUNT_REQUIRED",
                "message": "Le compte de reprise du résultat reste à déterminer "
                "avant comptabilisation.",
            }
        )
    return {
        "status": "PROVISIONAL",
        "read_only": True,
        "source_fiscal_year_id": previous.id,
        "source_end_date": previous.end_date.isoformat(),
        "target_fiscal_year_id": target.id,
        "opening_date": target.start_date.isoformat(),
        "excluded_draft_count": report["excluded_draft_count"],
        "target_entry_count": target_entries,
        "lines": lines,
        "previous_result": money(result),
        "result_line": result_line if result else None,
        "total_debit": money(total_debit),
        "total_credit": money(total_credit),
        "balanced": True,
        "warnings": warnings,
    }
