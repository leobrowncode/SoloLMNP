"""Start SoloLMNP locally without Docker (backend + frontend)."""

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
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = ROOT / ".venv"
DATA = ROOT / "data"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
UI_URL = "http://127.0.0.1:5173"
API_STATUS = "http://127.0.0.1:8000/api/status"


def die(message: str) -> None:
    print(f"SoloLMNP: {message}", file=sys.stderr, flush=True)
    raise SystemExit(1)


def require_python_312() -> None:
    if sys.version_info >= (3, 12):
        return
    found = sys.version.split()[0]
    hint = (
        "Installez Python 3.12+ (winget install -e --id Python.Python.3.12), "
        "puis relancez SoloLMNP.bat."
        if sys.platform == "win32"
        else "Installez Python 3.12+, puis relancez ./scripts/start_local.sh."
    )
    # Prefer re-exec via the Windows Python launcher when 3.12 is already present.
    if sys.platform == "win32" and shutil.which("py"):
        probe = subprocess.run(
            ["py", "-3.12", "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode == 0:
            target = probe.stdout.strip()
            if target and Path(target).is_file():
                os.execv(target, [target, *sys.argv])
    die(f"Python 3.12+ requis (trouvé {found}). {hint}")


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def venv_ready() -> bool:
    python = venv_python()
    if not python.is_file():
        return False
    probe = subprocess.run(
        [str(python), "-c", "import fastapi, uvicorn, alembic"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return probe.returncode == 0


def ensure_venv() -> Path:
    python = venv_python()
    if not python.is_file():
        print("Création de l'environnement Python (.venv)…")
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], cwd=ROOT, check=True)
    if not venv_ready():
        print("Installation des dépendances backend (premier lancement)…")
        subprocess.run(
            [str(python), "-m", "pip", "install", "--upgrade", "pip"],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(BACKEND / "requirements.lock")],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--no-build-isolation",
                "-e",
                str(BACKEND),
            ],
            cwd=ROOT,
            check=True,
        )
    return python


def ensure_frontend() -> str:
    npm = shutil.which("npm")
    if npm is None:
        die("Node.js / npm introuvable. Installez Node.js 24, puis relancez.")
    if not (FRONTEND / "node_modules").is_dir():
        print("Installation des dépendances frontend (npm ci)…")
        subprocess.run([npm, "ci"], cwd=FRONTEND, check=True)
    return npm


def ensure_env_and_data() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "documents").mkdir(parents=True, exist_ok=True)
    if not ENV_FILE.is_file():
        if ENV_EXAMPLE.is_file():
            ENV_FILE.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
            print("Fichier .env créé depuis .env.example.")
        else:
            die(".env.example manquant.")


def migrate(python: Path) -> None:
    print("Application des migrations…")
    subprocess.run(
        [str(python), "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        check=True,
    )


def wait_http(url: str, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.4)
    return False


def wait_owned(process: subprocess.Popen[bytes], url: str, label: str, timeout: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            die(f"Le {label} s'est arrêté pendant le démarrage (code {code}).")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.4)
    return False


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def ensure_ports_free() -> None:
    busy = []
    if port_in_use("127.0.0.1", 8000):
        busy.append("8000 (API)")
    if port_in_use("127.0.0.1", 5173):
        busy.append("5173 (interface)")
    if not busy:
        return
    ports = ", ".join(busy)
    die(
        f"Port(s) déjà utilisés : {ports}. "
        "Fermez l'ancienne fenêtre SoloLMNP, ou arrêtez le processus qui occupe "
        "ces ports, puis relancez."
    )


def stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()


def spawn(command: list[str], cwd: Path) -> subprocess.Popen[bytes]:
    if sys.platform == "win32":
        return subprocess.Popen(
            command,
            cwd=str(cwd),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # type: ignore[attr-defined]
        )
    return subprocess.Popen(command, cwd=str(cwd), start_new_session=True)


def main() -> None:
    # Keep progress visible in SoloLMNP.bat even when stdout is redirected.
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    require_python_312()
    if not (BACKEND / "app").is_dir() or not (FRONTEND / "package.json").is_file():
        die("Lancez ce script depuis le dépôt SoloLMNP.")

    python = ensure_venv()
    npm = ensure_frontend()
    ensure_env_and_data()
    migrate(python)
    ensure_ports_free()

    backend: subprocess.Popen[bytes] | None = None
    frontend: subprocess.Popen[bytes] | None = None
    print("Démarrage du backend (127.0.0.1:8000)…", flush=True)
    backend = spawn(
        [
            str(python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        BACKEND,
    )
    try:
        if not wait_owned(backend, API_STATUS, "backend"):
            die(
                "Le backend n'a pas répondu à temps. "
                "Vérifiez qu'aucune autre application n'utilise le port 8000."
            )
        print("Démarrage du frontend (127.0.0.1:5173)…", flush=True)
        frontend = spawn(
            [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
            FRONTEND,
        )
        if not wait_owned(frontend, UI_URL, "frontend"):
            die("Le frontend n'a pas répondu à temps. Vérifiez Node.js / npm.")
        print(f"SoloLMNP est prêt : {UI_URL}", flush=True)
        print("Tutoriel : docs/TUTORIAL.md", flush=True)
        print("Arrêt : Ctrl+C", flush=True)
        webbrowser.open(UI_URL)
        while True:
            if backend.poll() is not None:
                die(f"Le backend s'est arrêté (code {backend.returncode}).")
            if frontend.poll() is not None:
                die(f"Le frontend s'est arrêté (code {frontend.returncode}).")
            time.sleep(0.8)
    except KeyboardInterrupt:
        print("\nArrêt de SoloLMNP…", flush=True)
    finally:
        stop_process(frontend)
        stop_process(backend)


if __name__ == "__main__":
    main()
