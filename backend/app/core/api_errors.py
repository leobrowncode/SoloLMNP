"""Structured API error contract shared with the frontend."""

from __future__ import annotations

from typing import Any, NoReturn

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

RESOLUTION_ACTIONS: dict[str, dict[str, str]] = {
    "ACTIVITY_REQUIRED": {"label": "Ouvrir Comptabilité", "href": "/comptabilite"},
    "ACTIVITY_EXISTS": {"label": "Ouvrir Comptabilité", "href": "/comptabilite"},
    "FISCAL_NOT_COMPUTED": {"label": "Calculer la fiscalité", "href": "/fiscalite"},
    "CLOSE_BLOCKED": {"label": "Voir le pré-contrôle", "href": "/fiscalite"},
    "WARNINGS_UNACKNOWLEDGED": {"label": "Voir le pré-contrôle", "href": "/fiscalite"},
    "DATABASE_UNAVAILABLE": {"label": "Consulter la documentation", "href": "/"},
    "DATABASE_BUSY": {"label": "Réessayer dans un instant", "href": "/"},
    "INVENTORY_JOURNAL": {"label": "Plan comptable", "href": "/comptabilite/plan-comptable"},
    "RESULT_JOURNAL": {"label": "Plan comptable", "href": "/comptabilite/plan-comptable"},
    "BANK_REQUIRED": {"label": "Onglet Banque", "href": "/operations/banque"},
    "LOAN_PREVIEW_REQUIRED": {"label": "Onglet Emprunts", "href": "/operations/emprunts"},
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
        ),
    )


def import_line_fail(code: str, message: str, line: int, status: int = 422) -> NoReturn:
    fail(code, message, status, line=line, location="import")


def validation_issues(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for error in errors:
        location_parts = [str(part) for part in error.get("loc", ())]
        location = location_parts[0] if location_parts else "body"
        field = ".".join(location_parts[1:]) if len(location_parts) > 1 else None
        issues.append(
            {
                "code": str(error.get("type", "invalid")),
                "message": str(error.get("msg", "Valeur invalide.")),
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
            if "action" not in detail and isinstance(detail.get("code"), str):
                action = RESOLUTION_ACTIONS.get(detail["code"])
                if action:
                    detail = {**detail, "action": action}
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
                    message = str(item.get("msg", item.get("message", "Valeur invalide.")))
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
