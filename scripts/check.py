"""Run local quality checks with the active Python environment, on Windows or Linux."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(arguments: list[str], directory: Path) -> None:
    print(f"\n[{directory.name}] {' '.join(arguments)}", flush=True)
    subprocess.run(arguments, cwd=directory, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--backend-only", action="store_true")
    group.add_argument("--frontend-only", action="store_true")
    args = parser.parse_args()
    if not args.frontend_only:
        for command in (
            ["pip", "check"],
            ["ruff", "check", "."],
            ["ruff", "format", "--check", "."],
            ["mypy", "app"],
            ["pytest", "--cov=app", "--cov-report=term-missing"],
        ):
            run([sys.executable, "-m", *command], ROOT / "backend")
    if not args.backend_only:
        npm = shutil.which("npm")
        if npm is None:
            raise SystemExit(
                "npm is missing: install Node.js 24 and run npm ci in frontend/."
            )
        for name in ("lint", "typecheck", "test", "build"):
            run([npm, "run", name], ROOT / "frontend")


if __name__ == "__main__":
    main()
