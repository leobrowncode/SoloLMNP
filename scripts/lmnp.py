#!/usr/bin/env python3
"""Commande v1 : zéro secret, pas de Neon, pas de Postgres, pas de Vercel."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from lmnp_core.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
