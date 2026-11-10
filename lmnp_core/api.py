"""API fine au-dessus du noyau. Le calcul reste dans `build_dossier`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from lmnp_core.build import build_dossier, build_path
from lmnp_core.dossier import DossierError, dossier_from_mapping
from lmnp_core.sorties import pour_api, produire

app = FastAPI(title="SoloLMNP", version="1.0.0")


class Chemin(BaseModel):
    chemin: str = Field(min_length=1)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "produit": "sololmnp-v1"}


@app.post("/api/v1/build")
def build_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    """Construit depuis un chemin local ou depuis le JSON du dossier (même schéma que le YAML)."""
    try:
        if "chemin" in body and isinstance(body["chemin"], str):
            Chemin(chemin=body["chemin"])
            resultat = build_path(Path(body["chemin"]))
        else:
            resultat = build_dossier(dossier_from_mapping(body))
        corps = resultat.to_json()
        corps["sorties"] = pour_api(produire(resultat))
        return corps
    except DossierError as exc:
        return {"erreur": str(exc)}
