"""Single-user accounting API; schema changes are owned exclusively by Alembic."""

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
from app.api.filing import build_filing_router
from app.api.fiscal import build_fiscal_router
from app.api.ledger import build_ledger_router
from app.api.operations import build_operations_router
from app.core.api_errors import register_exception_handlers
from app.core.config import Settings, get_settings
from app.core.database import SCHEMA_REVISION, Database
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


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else get_settings()
    database = Database(configuration)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
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
        allow_headers=["Content-Type", "X-SoloLMNP-Request"],
    )
    application.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(configuration.allowed_hosts)
    )
    register_exception_handlers(application)

    @application.middleware("http")
    async def protect_writes(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            same_origin = str(request.base_url).rstrip("/")
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
        response.headers["Cache-Control"] = "no-store"
        return response

    application.include_router(build_ledger_router(database))
    application.include_router(build_operations_router(database))
    application.include_router(build_assets_router(database))
    application.include_router(build_fiscal_router(database))
    application.include_router(build_filing_router(database, configuration))

    @application.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/status", tags=["system"], response_model=ApplicationStatus)
    def status(response: Response) -> ApplicationStatus:
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
                }.issubset(tables)
        except SQLAlchemyError:
            # Never expose a local path, SQL statement or exception to the client.
            ready = False
        dossier: DossierStatus | None = None
        if ready:
            try:
                with database.sessions() as session:
                    dossier = DossierStatus.model_validate(current_dossier(session))
            except SQLAlchemyError:
                ready = False
                dossier = None
        response.status_code = 200 if ready else 503
        response.headers["Cache-Control"] = "no-store"
        on_cloud_drive = "onedrive" in str(configuration.database_path).lower()
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
