"""Démarre l'UI v1 et l'API noyau sans auth ni secret."""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
VENV = ROOT / ".venv"
UI_URL = "http://127.0.0.1:5173/v1/dossier"
API_HEALTH = "http://127.0.0.1:8000/api/health"


def die(message: str) -> None:
    print(f"SoloLMNP v1: {message}", file=sys.stderr, flush=True)
    raise SystemExit(1)


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def ensure_python() -> Path:
    python = venv_python()
    if python.is_file():
        return python
    print("Création de .venv et installation minimale…", flush=True)
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], cwd=ROOT, check=True)
    subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run(
        [str(python), "-m", "pip", "install", "fastapi", "uvicorn"],
        cwd=ROOT,
        check=True,
    )
    return python


def ensure_frontend() -> str:
    npm = shutil.which("npm")
    if npm is None:
        die("Node.js 24 requis.")
    if not (FRONTEND / "node_modules").is_dir():
        subprocess.run([npm, "ci"], cwd=FRONTEND, check=True)
    return npm


def port_busy(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait(url: str, proc: subprocess.Popen[bytes], label: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            die(f"{label} arrêté (code {proc.returncode}).")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.3)
    die(f"{label} n'a pas répondu.")


def spawn(cmd: list[str], cwd: Path) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT}{os.pathsep}{ROOT / 'backend'}"
    if sys.platform == "win32":
        return subprocess.Popen(cmd, cwd=str(cwd), env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)  # type: ignore[attr-defined]
    return subprocess.Popen(cmd, cwd=str(cwd), env=env, start_new_session=True)


def main() -> None:
    if port_busy(8000) or port_busy(5173):
        die("Ports 8000 ou 5173 occupés.")
    python = ensure_python()
    npm = ensure_frontend()
    backend = spawn([str(python), str(ROOT / "scripts" / "lmnp.py"), "serve"], ROOT)
    wait(API_HEALTH, backend, "API v1")
    frontend = spawn([npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"], FRONTEND)
    wait(UI_URL, frontend, "interface v1")
    print(f"SoloLMNP v1 prêt : {UI_URL}", flush=True)
    webbrowser.open(UI_URL)

    def stop(*_args: object) -> None:
        for proc in (frontend, backend):
            if proc.poll() is None:
                proc.terminate()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while True:
        for proc in (frontend, backend):
            if proc.poll() is not None:
                die("Un processus s'est arrêté.")
        time.sleep(0.8)


if __name__ == "__main__":
    main()
