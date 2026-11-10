"""API fine au-dessus du noyau. Le calcul reste dans `build_dossier`.

En local, `AUTH_MODE=local` ouvre un seul dossier, sans secret.
Ce mode est refusé en production et sur Vercel. Neon Auth et le jeton d'essai
réutilisent `app.core.auth`.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from app.core.auth import AuthError, ensure_email_allowed, verify_authorization
from app.core.config import Settings, local_mode_allowed
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from lmnp_core.depot import Depot, DepotFichiers
from lmnp_core.http import inclure_v1
from lmnp_core.persist import DATA_ROOT

_ENV = ("development", "production", "test")


def reglages_processus() -> Settings:
    app_env = os.environ.get("APP_ENV", "").strip() or "development"
    if app_env not in _ENV:
        app_env = "development"
    mode = os.environ.get("AUTH_MODE", "").strip()
    if not mode:
        mode = "local" if app_env == "development" and os.environ.get("VERCEL") != "1" else "neon"
    if mode == "local" and (app_env != "development" or os.environ.get("VERCEL") == "1"):
        raise RuntimeError("AUTH_MODE=local est refusé en production et sur Vercel.")
    emails = tuple(
        part.strip() for part in os.environ.get("ALLOWED_EMAILS", "").split(",") if part.strip()
    )
    return Settings(
        _env_file=None,
        app_env=app_env,  # type: ignore[arg-type]
        auth_mode=mode,  # type: ignore[arg-type]
        allowed_emails=emails,
        auth_test_secret=os.environ.get("AUTH_TEST_SECRET", ""),
        neon_auth_base_url=os.environ.get("NEON_AUTH_BASE_URL", ""),
        neon_auth_jwks_url=os.environ.get("NEON_AUTH_JWKS_URL", ""),
        allowed_hosts=("localhost", "127.0.0.1", "[::1]", "testserver"),
    )


def creer_app(depot: Depot | None = None, reglages: Settings | None = None) -> FastAPI:
    if reglages is None:
        reglages = reglages_processus()
    elif reglages.auth_mode == "local" and not local_mode_allowed(reglages):
        raise RuntimeError("AUTH_MODE=local est refusé en production et sur Vercel.")
    if depot is None:
        depot = DepotFichiers(DATA_ROOT)

    application = FastAPI(title="SoloLMNP", version="1.0.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def exiger_session(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        public = {"/api/health", "/api/auth/admission"}
        if request.method == "OPTIONS" or path in public or not path.startswith("/api/"):
            return await call_next(request)
        try:
            request.state.principal = verify_authorization(
                reglages, request.headers.get("authorization")
            )
        except AuthError as exc:
            return JSONResponse(
                status_code=exc.status,
                content={"detail": {"code": exc.code, "message": exc.message}},
                headers={"Cache-Control": "no-store"},
            )
        return await call_next(request)

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "produit": "sololmnp-v1"}

    @application.get("/api/auth/admission")
    def admission(email: str) -> dict[str, str]:
        try:
            ensure_email_allowed(reglages, email)
        except AuthError as exc:
            raise HTTPException(
                status_code=exc.status,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        return {"status": "allowed"}

    inclure_v1(application, depot)
    return application


app = creer_app()
