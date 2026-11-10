"""Vercel loads this module. Local v1 uses `python scripts/lmnp.py serve`.

One project serves the Vite build and the API under /api.
The v1 routes sit on the legacy app, behind its Neon Auth middleware.
On Vercel the dossier is a private Blob. Without the token the function
refuses to start, so a dossier is never written on the ephemeral disk.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_BACKEND = _ROOT / "backend"
for _entry in (str(_ROOT), str(_BACKEND)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from app.main import app as app  # noqa: E402
from app.services.blob_api import BlobNotFound, VercelBlobClient  # noqa: E402

from lmnp_core.depot import AdaptateurBlob, DepotBlob, DepotFichiers  # noqa: E402
from lmnp_core.http import inclure_v1  # noqa: E402
from lmnp_core.persist import DATA_ROOT  # noqa: E402


def _depot_v1() -> DepotFichiers | DepotBlob:
    if os.environ.get("VERCEL") == "1":
        token = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "BLOB_READ_WRITE_TOKEN est requis sur Vercel : "
                "le dossier v1 ne tient pas sur le disque de la fonction."
            )
        return DepotBlob(AdaptateurBlob(VercelBlobClient(token), (BlobNotFound,)))
    return DepotFichiers(DATA_ROOT)


inclure_v1(app, _depot_v1())

_DIST = _ROOT / "frontend" / "dist"
if os.environ.get("VERCEL") == "1" and _DIST.is_dir():
    app.frontend("/", directory=_DIST, fallback="index.html", check_dir=False)
