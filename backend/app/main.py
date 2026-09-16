"""Read-only foundation API; schema changes are owned exclusively by Alembic."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import Settings, get_settings
from app.core.database import SCHEMA_REVISION, Database

APPLICATION_VERSION = "0.2.0"


class DatabaseStatus(BaseModel):
    status: Literal["ready", "not_ready"]
    schema_revision: str | None
    expected_revision: str = SCHEMA_REVISION


class FiscalStatus(BaseModel):
    status: Literal["research_only"] = "research_only"
    available_vintages: list[str] = Field(default_factory=list)


class ApplicationStatus(BaseModel):
    application_version: str = APPLICATION_VERSION
    phase: Literal["foundation"] = "foundation"
    database: DatabaseStatus
    fiscal: FiscalStatus = Field(default_factory=FiscalStatus)


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
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )
    application.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(configuration.allowed_hosts)
    )

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
                }.issubset(tables)
        except SQLAlchemyError:
            # Never expose a local path, SQL statement or exception to the client.
            ready = False
        response.status_code = 200 if ready else 503
        response.headers["Cache-Control"] = "no-store"
        return ApplicationStatus(
            database=DatabaseStatus(
                status="ready" if ready else "not_ready",
                schema_revision=revision,
            )
        )

    return application


app = create_app()
