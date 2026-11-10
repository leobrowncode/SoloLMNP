"""CLI `lmnp build` et `lmnp serve`. Aucun secret."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from lmnp_core.build import build_path
from lmnp_core.dossier import DossierError


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print("Usage : python scripts/lmnp.py build <dossier> | serve")
        return 0
    if args[0] == "serve":
        import uvicorn

        uvicorn.run("lmnp_core.api:app", host="127.0.0.1", port=8000, factory=False)
        return 0
    if args[0] != "build" or len(args) != 2:
        print("Usage : python scripts/lmnp.py build <dossier>", file=sys.stderr)
        return 2
    try:
        resultat = build_path(Path(args[1]))
    except DossierError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(resultat.to_json(), ensure_ascii=False, indent=2))
    return 0
