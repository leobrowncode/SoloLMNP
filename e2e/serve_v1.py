"""Lance l'API noyau v1 et le frontend pour les tests Playwright du parcours /v1."""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
API = "http://127.0.0.1:8000/api/health"
UI = "http://127.0.0.1:5173/v1/dossier"


def port_free(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def wait(url: str, proc: subprocess.Popen[bytes], label: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"{label} arrêté ({proc.returncode}).")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except OSError:
            time.sleep(0.3)
    raise SystemExit(f"{label} sans réponse.")


def arreter(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    if os.name != "nt":
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            return
        except (ProcessLookupError, PermissionError):
            pass
    proc.terminate()


def spawn(cmd: list[str], cwd: Path) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.pop("VERCEL", None)
    env["APP_ENV"] = "development"
    env["AUTH_MODE"] = "local"
    env["VITE_AUTH_MODE"] = "local"
    env["PYTHONPATH"] = f"{ROOT}{os.pathsep}{ROOT / 'backend'}"
    if sys.platform == "win32":
        return subprocess.Popen(cmd, cwd=str(cwd), env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)  # type: ignore[attr-defined]
    return subprocess.Popen(cmd, cwd=str(cwd), env=env, start_new_session=True)


def main() -> None:
    for port in (8000, 5173):
        if not port_free(port):
            raise SystemExit(f"Port {port} occupé.")
    npm = "npm.cmd" if os.name == "nt" else (shutil.which("npm") or "npm")
    python = sys.executable
    children: list[subprocess.Popen[bytes]] = []

    def stop(*_args: object) -> None:
        for child in children:
            arreter(child)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    children.append(spawn([python, str(ROOT / "scripts" / "lmnp.py"), "serve"], ROOT))
    wait(API, children[0], "API v1")
    children.append(
        spawn([npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"], FRONTEND)
    )
    wait(UI, children[1], "frontend v1")
    print("E2E v1 prêt.", flush=True)
    while True:
        for child in children:
            if child.poll() is not None:
                stop()
        time.sleep(0.5)


if __name__ == "__main__":
    main()
