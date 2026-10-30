"""Start a throwaway API and the Vite dev server for browser tests.

The database and documents live in a temporary directory. Nothing is written
under data/.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
API = "http://127.0.0.1:8000/api/health"
UI = "http://127.0.0.1:5173"


def port_free(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def wait_http(url: str, proc: subprocess.Popen[bytes], label: str) -> None:
    import urllib.request

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"{label} s’est arrêté avant d’écouter ({proc.returncode}).")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except OSError:
            time.sleep(0.2)
    raise SystemExit(f"{label} n’a pas répondu à temps.")


def main() -> None:
    for port, name in ((8000, "API"), (5173, "interface")):
        if not port_free(port):
            raise SystemExit(f"Le port {port} ({name}) est déjà utilisé.")
    temporary = tempfile.mkdtemp(prefix="sololmnp-e2e-")
    reuse = os.environ.get("SOLOLMNP_E2E_DATABASE", "").strip()
    database = Path(reuse) if reuse else Path(temporary) / "sololmnp.sqlite3"
    documents = Path(temporary) / "documents"
    documents.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": f"sqlite:///{database.as_posix()}",
            "DOCUMENTS_DIR": str(documents),
            "CORS_ORIGINS": "[]",
            "ALLOWED_HOSTS": "localhost,127.0.0.1,testserver",
        }
    )
    print(f"Base temporaire : {database}", flush=True)
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        check=False,
    )
    if migration.returncode != 0:
        raise SystemExit("Migration Alembic refusée.")
    children: list[subprocess.Popen[bytes]] = []

    def stop(*_args: object) -> None:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    children.append(
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=BACKEND,
            env=env,
        )
    )
    wait_http(API, children[0], "API")
    npm = "npm.cmd" if os.name == "nt" else "npm"
    children.append(
        subprocess.Popen(
            [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
            cwd=FRONTEND,
            env=env,
        )
    )
    wait_http(UI, children[1], "interface")
    print("SoloLMNP E2E prêt.", flush=True)
    while True:
        for child in children:
            if child.poll() is not None:
                stop()
        time.sleep(0.5)


if __name__ == "__main__":
    main()
