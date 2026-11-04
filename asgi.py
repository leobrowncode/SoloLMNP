"""Vercel loads this module. Local and Docker keep using uvicorn app.main:app.

One project serves the Vite build as static files and this API under /api.
Routes stay /api/... : the platform passes the original path to the function.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.main import app as app  # noqa: E402

_DIST = _ROOT / "frontend" / "dist"
if os.environ.get("VERCEL") == "1" and _DIST.is_dir():
    app.frontend("/", directory=_DIST, fallback="index.html", check_dir=False)
