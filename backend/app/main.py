"""Single-user accounting API; schema changes are owned exclusively by Alembic."""

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal, Self

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.assets import build_assets_router
from app.api.dashboard import build_dashboard_router
from app.api.filing import build_filing_router
from app.api.fiscal import build_fiscal_router
from app.api.ledger import build_ledger_router
from app.api.operations import build_operations_router
from app.core.api_errors import register_exception_handlers
from app.core.auth import AuthError, ensure_email_allowed, verify_authorization
from app.core.config import Settings, deployment_hosts, get_settings, local_mode_allowed
from app.core.database import SCHEMA_REVISION, Database
from app.core.ownership import resolve_owner_id
from app.core.version import APPLICATION_VERSION
from app.domain.fiscal.loader import available_vintages
from app.services.dossier import current_dossier


class DatabaseStatus(BaseModel):
    status: Literal["ready", "not_ready"]
    schema_revision: str | None
    expected_revision: str = SCHEMA_REVISION


class FiscalStatus(BaseModel):
    status: Literal["research_only"] = "research_only"
    available_vintages: list[str] = Field(default_factory=list)


_DOSSIER_LABELS = {
    "incomplet": "Incomplet",
    "bloque": "Bloqué",
    "pret_a_verifier": "Prêt à vérifier",
    "cloture": "Clôturé",
}


class DossierStatus(BaseModel):
    status: Literal["incomplet", "bloque", "pret_a_verifier", "cloture"]
    label: Literal["Incomplet", "Bloqué", "Prêt à vérifier", "Clôturé"]
    fiscal_year_id: int | None
    year: int | None
    year_status: Literal["OPEN", "READY_TO_CLOSE", "CLOSED"] | None
    vintage_status: Literal["research_only"]

    @model_validator(mode="after")
    def label_matches_status(self) -> Self:
        if self.label != _DOSSIER_LABELS[self.status]:
            raise ValueError("Le libellé du dossier ne correspond pas à son statut.")
        return self


class ApplicationStatus(BaseModel):
    application_version: str = APPLICATION_VERSION
    phase: Literal["assets"] = "assets"
    database: DatabaseStatus
    fiscal: FiscalStatus = Field(default_factory=FiscalStatus)
    storage_warning: str | None = None
    dossier: DossierStatus | None = None


def _request_origin(request: Request) -> str:
    """On Vercel the edge terminates TLS. Trust its proto only there."""
    if os.environ.get("VERCEL") == "1":
        forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
        host = request.headers.get("host", "")
        if forwarded in {"http", "https"} and host:
            return f"{forwarded}://{host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def _refuse_auth_bypass(configuration: Settings) -> None:
    """Production and Vercel accept Neon Auth only. Local mode cannot be constructed around this."""
    on_vercel = os.environ.get("VERCEL") == "1"
    if configuration.auth_mode == "test" and (configuration.app_env == "production" or on_vercel):
        raise RuntimeError("AUTH_MODE=test est refusé en production.")
    if configuration.auth_mode == "local" and not local_mode_allowed(configuration):
        raise RuntimeError("AUTH_MODE=local est refusé en production et sur Vercel.")
    if (configuration.app_env == "production" or on_vercel) and configuration.auth_mode != "neon":
        raise RuntimeError("Seul Neon Auth est accepté en production et sur Vercel.")


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else get_settings()
    _refuse_auth_bypass(configuration)
    database = Database(configuration)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if configuration.uses_sqlite:
            configuration.database_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            yield
        finally:
            database.engine.dispose()

    application = FastAPI(
        title="SoloLMNP",
        version=APPLICATION_VERSION,
        lifespan=lifespan,
        docs_url="/api/docs" if configuration.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if configuration.app_env != "production" else None,
    )
    application.state.database = database
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(configuration.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-SoloLMNP-Request"],
    )
    hosts = tuple(dict.fromkeys((*configuration.allowed_hosts, *deployment_hosts())))
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=list(hosts))
    register_exception_handlers(application)

    @application.middleware("http")
    async def require_session(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        public = {"/api/health", "/api/auth/admission"}
        if request.method == "OPTIONS" or path in public or not path.startswith("/api/"):
            return await call_next(request)
        try:
            request.state.principal = verify_authorization(
                configuration, request.headers.get("authorization")
            )
        except AuthError as exc:
            return JSONResponse(
                status_code=exc.status,
                content={"detail": {"code": exc.code, "message": exc.message}},
                headers={"Cache-Control": "no-store"},
            )
        return await call_next(request)

    @application.middleware("http")
    async def protect_writes(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            same_origin = _request_origin(request)
            if (
                request.headers.get("x-sololmnp-request") != "1"
                or (origin is not None and origin not in {same_origin, *configuration.cors_origins})
                or request.headers.get("sec-fetch-site") == "cross-site"
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": {
                            "code": "ORIGIN_REJECTED",
                            "message": "Requête d’écriture non autorisée depuis cette origine.",
                        }
                    },
                )
        response = await call_next(request)
        if "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response

    application.include_router(build_dashboard_router(database))
    application.include_router(build_ledger_router(database))
    application.include_router(build_operations_router(database))
    application.include_router(build_assets_router(database))
    application.include_router(build_fiscal_router(database))
    application.include_router(build_filing_router(database, configuration))

    @application.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/auth/admission", tags=["system"])
    def admission(email: str) -> dict[str, str]:
        try:
            ensure_email_allowed(configuration, email)
        except AuthError as exc:
            return JSONResponse(
                status_code=exc.status,
                content={"detail": {"code": exc.code, "message": exc.message}},
                headers={"Cache-Control": "no-store"},
            )
        return {"status": "allowed"}

    @application.get("/api/status", tags=["system"], response_model=ApplicationStatus)
    def status(request: Request, response: Response) -> ApplicationStatus:
        revision: str | None = None
        ready = False
        try:
            with database.engine.connect() as connection:
                tables = set(inspect(connection).get_table_names())
                if "alembic_version" in tables:
                    revision = connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one_or_none()
                ready = revision == SCHEMA_REVISION and {
                    "rental_activity",
                    "property",
                    "fiscal_year",
                    "account",
                    "accounting_journal",
                    "accounting_entry",
                    "accounting_entry_line",
                    "ledger_event",
                    "business_operation",
                    "bank_account",
                    "bank_transaction",
                    "bank_match",
                    "loan",
                    "asset",
                    "asset_component",
                    "depreciation_schedule",
                    "depreciation_period",
                    "fiscal_computation",
                    "depreciation_carry_forward",
                    "tax_loss_carry_forward",
                    "audit_event",
                    "tax_return_snapshot",
                    "supporting_document",
                    "tenant",
                    "app_account",
                    "dossier_archive",
                }.issubset(tables)
        except SQLAlchemyError:
            # Never expose a local path, SQL statement or exception to the client.
            ready = False
        dossier: DossierStatus | None = None
        if ready:
            try:
                owner_id = resolve_owner_id(database, request.state.principal)
                with database.sessions() as session:
                    session.info["owner_id"] = owner_id
                    dossier = DossierStatus.model_validate(current_dossier(session))
            except SQLAlchemyError:
                ready = False
                dossier = None
        response.status_code = 200 if ready else 503
        response.headers["Cache-Control"] = "no-store"
        on_cloud_drive = configuration.uses_sqlite and (
            "onedrive" in str(configuration.database_path).lower()
        )
        return ApplicationStatus(
            database=DatabaseStatus(
                status="ready" if ready else "not_ready",
                schema_revision=revision,
            ),
            fiscal=FiscalStatus(available_vintages=available_vintages() if ready else []),
            storage_warning=(
                "La base est dans un dossier synchronisé (OneDrive). "
                "Copiez le projet hors de ce dossier : la synchro peut corrompre SQLite."
                if on_cloud_drive
                else None
            ),
            dossier=dossier,
        )

    return application


app = create_app()
