"""Exercise Docker on disposable data; never mounts the user's data directory."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("Docker with Compose v2 is required for this smoke test.")
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    gid = os.getgid() if hasattr(os, "getgid") else 1000
    if uid == 0:
        raise SystemExit(
            "Run this test as a regular user; containers use the data owner's UID."
        )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    project = f"sololmnp-smoke-{uuid.uuid4().hex[:12]}"
    with tempfile.TemporaryDirectory(prefix="sololmnp-smoke-") as temporary:
        environment = os.environ.copy()
        environment.update(
            SOLOLMNP_DATA_DIR=str(Path(temporary).resolve()),
            SOLOLMNP_PORT=str(port),
            SOLOLMNP_UID=str(uid),
            SOLOLMNP_GID=str(gid),
            ALLOWED_HOSTS="localhost,127.0.0.1,[::1]",
        )
        compose = [
            docker,
            "compose",
            "--project-name",
            project,
            "-f",
            str(ROOT / "docker-compose.yml"),
        ]

        def run(
            *arguments: str, capture: bool = False, check: bool = True
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [*compose, *arguments],
                cwd=ROOT,
                env=environment,
                check=check,
                text=True,
                capture_output=capture,
            )

        def http_check() -> None:
            base = f"http://127.0.0.1:{port}"
            with urllib.request.urlopen(base + "/", timeout=10) as response:
                assert response.status == 200
                assert b'<div id="root">' in response.read()
                assert response.headers["X-Content-Type-Options"] == "nosniff"
            for route in ("/api/health", "/api/status"):
                with urllib.request.urlopen(base + route, timeout=10) as response:
                    assert response.status == 200
                    assert isinstance(json.load(response), dict)

        try:
            run("up", "--build", "--detach", "--wait", "--wait-timeout", "180")
            http_check()
            for service in ("backend", "frontend"):
                assert (
                    run("exec", "-T", service, "id", "-u", capture=True).stdout.strip()
                    != "0"
                )
            run(
                "exec",
                "-T",
                "backend",
                "python",
                "-c",
                "import sqlite3; from pathlib import Path; "
                "from alembic.config import Config; from alembic.script import ScriptDirectory; "
                "path=Path('/app/data/sololmnp.sqlite3'); assert path.is_file(); "
                "db=sqlite3.connect(path); "
                "assert db.execute('select version_num from alembic_version').fetchone()[0] "
                "== ScriptDirectory.from_config(Config('alembic.ini')).get_current_head(); "
                "db.execute('create table ci_persistence_probe (value text not null)'); "
                "db.execute('insert into ci_persistence_probe values (?)', ('fictitious',)); "
                "db.commit(); db.close(); "
                "Path('/app/data/ci-document.txt').write_text('fictitious', encoding='utf-8')",
            )
            run("up", "--detach", "--force-recreate", "--wait", "--wait-timeout", "180")
            http_check()
            run(
                "exec",
                "-T",
                "backend",
                "python",
                "-c",
                "import sqlite3; from pathlib import Path; "
                "db=sqlite3.connect('/app/data/sololmnp.sqlite3'); "
                "assert db.execute('select value from ci_persistence_probe').fetchone()[0] "
                "== 'fictitious'; db.close(); "
                "assert Path('/app/data/ci-document.txt').read_text(encoding='utf-8') == 'fictitious'",
            )
            print(
                "Docker smoke passed: HTTP, readiness, non-root, migrations and persisted data."
            )
        except BaseException:
            run("logs", "--no-color", check=False)
            raise
        finally:
            run("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
