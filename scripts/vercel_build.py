"""Vercel build: Vite bundle, then one Alembic upgrade on the direct URL.

Local and Docker do not run this script. They migrate at process start, on SQLite.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import psycopg  # noqa: E402

from app.core.vercel_deploy import (  # noqa: E402
    DeployGuardError,
    advisory_migration_lock,
    plan_migration,
    psycopg_dsn,
)


def main() -> None:
    vercel_env = os.environ.get("VERCEL_ENV", "")
    deploying = os.environ.get("VERCEL") == "1" and vercel_env in {"preview", "production"}
    if deploying:
        if os.environ.get("VERCEL_FASTAPI_STATIC_CDN", "").lower() not in {"1", "true"}:
            print(
                "Avertissement : VERCEL_FASTAPI_STATIC_CDN n’est pas à 1. "
                "Sans cette variable, le builder peut garder le frontend dans la fonction "
                "au lieu du CDN.",
                flush=True,
            )
        try:
            plan = plan_migration(os.environ)
        except DeployGuardError as exc:
            raise SystemExit(str(exc)) from None
    else:
        plan = None
        print("Hors déploiement Vercel : migration ignorée.", flush=True)

    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("npm est absent. Le build Vercel exige Node.js 24.")
    subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)
    index = ROOT / "frontend" / "dist" / "index.html"
    if not index.is_file():
        raise SystemExit("Le build Vite n’a pas produit frontend/dist/index.html.")

    if plan is None:
        return
    print(f"Alembic upgrade head vers {plan.host} ({plan.vercel_env}).", flush=True)
    migration_env = os.environ.copy()
    migration_env["DATABASE_URL"] = plan.sqlalchemy_url
    try:
        with psycopg.connect(
            psycopg_dsn(plan.sqlalchemy_url),
            autocommit=True,
            connect_timeout=15,
        ) as connection:
            with advisory_migration_lock(connection):
                subprocess.run(
                    [sys.executable, "-m", "alembic", "upgrade", "head"],
                    cwd=ROOT / "backend",
                    env=migration_env,
                    check=True,
                )
    except DeployGuardError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
