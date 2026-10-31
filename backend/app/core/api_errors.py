"""Structured API error contract shared with the frontend."""

from __future__ import annotations

from typing import Any, NoReturn

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Glossary ids from frontend/src/features/glossary.ts. Keep in sync with ERROR_HELP.
HELP_IDS: dict[str, str] = {
    "ALREADY_MATCHED": "rapprochement",
    "ALREADY_REVERSED": "extourne",
    "BANK_MATCH_EXISTS": "rapprochement",
    "BUSINESS_REVERSAL_REQUIRED": "extourne",
    "CLOSE_BLOCKED": "cloture",
    "DEPRECIATION_TARGET_NOT_FOUND": "amortissement",
    "EMPTY_OPENING": "a-nouveaux",
    "EXPORT_BLOCKED": "liasse",
    "FEC_INVALID": "fec",
    "FISCAL_NOT_COMPUTED": "resultat-fiscal",
    "FISCAL_RULE_BLOCKED": "cession",
    "LOAN_ACCOUNT_EXHAUSTED": "compte-164",
    "LOAN_NOT_FUNDED": "compte-164",
    "LOAN_OPENING_BALANCE": "emprunt",
    "MAPPING_MISSING": "millesime",
    "MAPPING_UNUSABLE": "millesime",
    "MATCH_INCONSISTENT": "rapprochement",
    "NOT_MATCHED": "rapprochement",
    "NOT_VALIDATED": "extourne",
    "OPENING_ALREADY_EXISTS": "a-nouveaux",
    "OPENING_AUDIT_MISSING": "a-nouveaux",
    "OPENING_JOURNAL_REQUIRED": "a-nouveaux",
    "OPENING_TOO_LARGE": "a-nouveaux",
    "PREVIOUS_YEAR_REQUIRED": "a-nouveaux",
    "PRINCIPAL_EXCEEDED": "compte-164",
    "RESULT_ACCOUNT_REQUIRED": "compte-120-129",
    "REVERSAL_CHAIN": "extourne",
    "REVERSAL_DATE": "extourne",
    "SCHEDULE_NOT_FOUND": "amortissement",
    "SETTLEMENTS_EXIST": "extourne",
    "SIREN_MANQUANT": "siren",
    "SIREN_REQUIRED": "siren",
    "SOURCE_NOT_CLOSED": "a-nouveaux",
    "TARGET_HAS_ENTRIES": "a-nouveaux",
    "UNBALANCED_OPENING": "a-nouveaux",
    "UNKNOWN_VINTAGE": "millesime",
    "VINTAGE_NOT_USABLE": "millesime",
    "WARNINGS_UNACKNOWLEDGED": "pre-controle",
    "YEAR_NOT_CLOSED": "cloture",
    "BANK_REQUIRED": "compte-512",
    "CSV_AMOUNT": "import-csv",
    "CSV_CONFLICT": "import-csv",
    "CSV_EMPTY": "import-csv",
    "CSV_HEADER": "import-csv",
    "CSV_INVALID": "import-csv",
    "CSV_PAID": "import-csv",
    "CSV_PROFILE": "import-csv",
    "CSV_REFERENCE": "import-csv",
    "CSV_SHAPE": "import-csv",
    "CSV_TYPE": "import-csv",
    "CSV_ZERO": "import-csv",
    "DATE_OUTSIDE_YEAR": "exercice",
    "LOAN_CHRONOLOGY": "emprunt",
    "LOAN_CSV_AMOUNT": "import-csv",
    "LOAN_CSV_BEFORE_START": "emprunt",
    "LOAN_CSV_CONFLICT": "emprunt",
    "LOAN_CSV_DATE": "import-csv",
    "LOAN_CSV_DUPLICATE_DATE": "import-csv",
    "LOAN_CSV_DUPLICATE_PAYMENT_DATE": "import-csv",
    "LOAN_CSV_EMPTY": "import-csv",
    "LOAN_CSV_EXTERNAL_INSURANCE": "emprunt",
    "LOAN_CSV_HEADER": "import-csv",
    "LOAN_CSV_INVALID": "import-csv",
    "LOAN_CSV_MULTIPLE_LOANS": "emprunt",
    "LOAN_CSV_REFERENCE": "import-csv",
    "LOAN_CSV_SHAPE": "import-csv",
    "LOAN_CSV_SPLIT": "emprunt",
    "LOAN_PREVIEW_REQUIRED": "emprunt",
    "BACKUP_NOT_FOUND": "sauvegarde",
    "BACKUP_PATH": "sauvegarde",
    "BACKUP_REJECTED": "sauvegarde",
    "DOCUMENT_NOT_FOUND": "justificatif",
    "DOCUMENT_PATH": "justificatif",
    "DOCUMENT_SIGNATURE": "justificatif",
    "DOCUMENT_SIZE": "justificatif",
    "ENTRY_AMBIGUOUS": "ecriture",
    "ENTRY_NOT_FOUND": "ecriture",
    "ENTRY_SEARCH": "ecriture",
    "INVALID_DOCUMENT": "justificatif",
    "RESTORE_CONFIRMATION": "restauration",
    "BATCH_INTERRUPTED": "dotation",
    "IDEMPOTENCY_CONFLICT": "dotation",
    "IDEMPOTENCY_KEY_REQUIRED": "dotation",
    "IDEMPOTENCY_RECORD_INVALID": "dotation",
    "PERIOD_NOT_FOUND": "dotation",
    "PERIOD_YEAR_MISMATCH": "dotation",
    "ZERO_DEPRECIATION": "dotation",
}

RESOLUTION_ACTIONS: dict[str, dict[str, str]] = {
    "ACTIVITY_REQUIRED": {"label": "Ouvrir Comptabilité", "href": "/comptabilite"},
    "ACTIVITY_EXISTS": {"label": "Ouvrir Comptabilité", "href": "/comptabilite"},
    "FISCAL_NOT_COMPUTED": {"label": "Calculer la fiscalité", "href": "/fiscalite#calcul-fiscal"},
    "FISCAL_RULE_BLOCKED": {
        "label": "Voir les règles bloquées",
        "href": "/fiscalite#regles-lmnp",
    },
    "CLOSE_BLOCKED": {"label": "Voir le pré-contrôle", "href": "/fiscalite"},
    "WARNINGS_UNACKNOWLEDGED": {"label": "Voir le pré-contrôle", "href": "/fiscalite"},
    "YEAR_NOT_CLOSED": {"label": "Clôturer l’exercice", "href": "/fiscalite#close-title"},
    "SIREN_REQUIRED": {
        "label": "Renseigner le SIREN",
        "href": "/comptabilite/brouillons#identite-liasse",
    },
    "SIREN_MANQUANT": {
        "label": "Renseigner le SIREN",
        "href": "/comptabilite/brouillons#identite-liasse",
    },
    "FEC_INVALID": {"label": "Voir le pré-contrôle", "href": "/fiscalite#close-title"},
    "EXPORT_BLOCKED": {"label": "Voir la liasse", "href": "/fiscalite#sorties-figees"},
    "DATABASE_UNAVAILABLE": {"label": "Consulter la documentation", "href": "/"},
    "DATABASE_BUSY": {"label": "Réessayer dans un instant", "href": "/"},
    "INVENTORY_JOURNAL": {"label": "Plan comptable", "href": "/comptabilite/plan-comptable"},
    "RESULT_JOURNAL": {"label": "Plan comptable", "href": "/comptabilite/plan-comptable"},
    "BANK_REQUIRED": {"label": "Onglet Banque", "href": "/operations/banque"},
    "LOAN_PREVIEW_REQUIRED": {"label": "Onglet Emprunts", "href": "/operations/emprunts"},
    "BACKUP_NOT_FOUND": {"label": "Voir les sauvegardes", "href": "/conservation#sauvegardes"},
    "BACKUP_REJECTED": {"label": "Contrôler la sauvegarde", "href": "/conservation#sauvegardes"},
    "DOCUMENT_NOT_FOUND": {
        "label": "Voir les justificatifs",
        "href": "/conservation#justificatifs",
    },
    "ENTRY_AMBIGUOUS": {"label": "Choisir une écriture", "href": "/conservation#entry-picker"},
    "ENTRY_NOT_FOUND": {"label": "Choisir une écriture", "href": "/conservation#entry-picker"},
    "ENTRY_SEARCH": {"label": "Choisir une écriture", "href": "/conservation#entry-picker"},
    "RESTORE_CONFIRMATION": {
        "label": "Saisir RESTAURER",
        "href": "/conservation#restore-confirmation",
    },
    "IDEMPOTENCY_CONFLICT": {
        "label": "Revenir aux dotations",
        "href": "/immobilisations#dotations",
    },
    "IDEMPOTENCY_KEY_REQUIRED": {
        "label": "Revenir aux dotations",
        "href": "/immobilisations#dotations",
    },
    "PERIOD_NOT_FOUND": {
        "label": "Revenir aux dotations",
        "href": "/immobilisations#dotations",
    },
    "PERIOD_YEAR_MISMATCH": {
        "label": "Revenir aux dotations",
        "href": "/immobilisations#dotations",
    },
    "ZERO_DEPRECIATION": {
        "label": "Revenir aux dotations",
        "href": "/immobilisations#dotations",
    },
    "ASSET_NOT_BOOKED": {
        "label": "Faire entrer le bien en comptabilité",
        "href": "/immobilisations#entree-bien",
    },
    "ASSET_PURCHASE_UNBOOKED": {
        "label": "Inscrire l’immobilisation au journal",
        "href": "/comptabilite/brouillons#nouvelle-ecriture",
    },
    "IMMOBILISATIONS_ECART": {
        "label": "Faire entrer le bien en comptabilité",
        "href": "/immobilisations#entree-bien",
    },
    "IMMOBILISATIONS_NETTES_NEGATIVES": {
        "label": "Faire entrer le bien en comptabilité",
        "href": "/immobilisations#entree-bien",
    },
    "CENTRALIZATION_STALE": {
        "label": "Revoir la centralisation",
        "href": "/etats-comptables#result-title",
    },
}


def _detail(
    code: str,
    message: str,
    *,
    field: str | None = None,
    location: str | None = None,
    line: int | None = None,
    action: dict[str, str] | None = None,
    issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if field:
        payload["field"] = field
    if location:
        payload["location"] = location
    if line is not None:
        payload["line"] = line
    resolved = action or RESOLUTION_ACTIONS.get(code)
    if resolved:
        payload["action"] = resolved
    help_id = HELP_IDS.get(code)
    if help_id:
        payload["help"] = help_id
    if issues:
        payload["issues"] = issues
    return payload


def fail(
    code: str,
    message: str,
    status: int = 409,
    *,
    field: str | None = None,
    location: str | None = None,
    line: int | None = None,
    action: dict[str, str] | None = None,
    issues: list[dict[str, Any]] | None = None,
) -> NoReturn:
    raise HTTPException(
        status_code=status,
        detail=_detail(
            code,
            message,
            field=field,
            location=location,
            line=line,
            action=action,
            issues=issues,
        ),
    )


def import_line_fail(code: str, message: str, line: int, status: int = 422) -> NoReturn:
    fail(code, message, status, line=line, location="import")


def readable_validation_message(message: object) -> str:
    text = str(message or "Valeur invalide.")
    prefix = "Value error, "
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


def validation_issues(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for error in errors:
        location_parts = [str(part) for part in error.get("loc", ())]
        location = location_parts[0] if location_parts else "body"
        field = ".".join(location_parts[1:]) if len(location_parts) > 1 else None
        issues.append(
            {
                "code": str(error.get("type", "invalid")),
                "message": readable_validation_message(error.get("msg", "Valeur invalide.")),
                "field": field,
                "location": location,
            }
        )
    return issues


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        issues = validation_issues(list(exc.errors()))
        return JSONResponse(
            status_code=422,
            content={
                "detail": _detail(
                    "VALIDATION_ERROR",
                    "Les données envoyées sont invalides.",
                    issues=issues,
                )
            },
        )

    @application.exception_handler(HTTPException)
    async def handle_http(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
            detail = dict(exc.detail)
            if isinstance(detail.get("code"), str):
                if "action" not in detail:
                    action = RESOLUTION_ACTIONS.get(detail["code"])
                    if action:
                        detail = {**detail, "action": action}
                if "help" not in detail:
                    help_id = HELP_IDS.get(detail["code"])
                    if help_id:
                        detail = {**detail, "help": help_id}
            return JSONResponse(status_code=exc.status_code, content={"detail": detail})
        if isinstance(exc.detail, str):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": _detail("HTTP_ERROR", exc.detail)},
            )
        if isinstance(exc.detail, list):
            issues = []
            for item in exc.detail:
                if isinstance(item, dict):
                    loc = item.get("loc", ())
                    if isinstance(loc, (list, tuple)):
                        location_parts = [str(part) for part in loc]
                    else:
                        location_parts = []
                    location = location_parts[0] if location_parts else "body"
                    if len(location_parts) > 1:
                        field = ".".join(location_parts[1:])
                    else:
                        field = item.get("field")
                    message = readable_validation_message(
                        item.get("msg", item.get("message", "Valeur invalide."))
                    )
                    issues.append(
                        {
                            "code": str(item.get("type", item.get("code", "invalid"))),
                            "message": message,
                            "field": field if isinstance(field, str) else None,
                            "location": location,
                        }
                    )
                elif isinstance(item, str):
                    issues.append(
                        {
                            "code": "invalid",
                            "message": item,
                            "field": None,
                            "location": "body",
                        }
                    )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "detail": _detail(
                        "VALIDATION_ERROR",
                        "Les données envoyées sont invalides.",
                        issues=issues,
                    )
                },
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": _detail("HTTP_ERROR", "Opération refusée.")},
        )
