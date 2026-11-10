"""API fine au-dessus du noyau. Le calcul reste dans `build_dossier`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from lmnp_core.build import build_dossier, build_path
from lmnp_core.dossier import DossierError, dossier_from_mapping
from lmnp_core.persist import (
    assurer_data,
    categories_annee,
    creer_dossier,
    enregistrer,
    lister_modeles,
    lire_chemin,
)
from lmnp_core.siret import valide as siret_valide
from lmnp_core.sorties import pour_api, produire

app = FastAPI(title="SoloLMNP", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Chemin(BaseModel):
    chemin: str = Field(min_length=1)


class Enregistrement(BaseModel):
    chemin: str | None = None
    dossier: dict[str, Any]
    mouvements: list[dict[str, Any]] | None = None


class Creation(BaseModel):
    modele: str = Field(min_length=1)
    nom: str = Field(min_length=1, pattern=r"^[a-z0-9-]+$")


class SiretBody(BaseModel):
    siret: str = Field(min_length=14, max_length=14)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "produit": "sololmnp-v1"}


@app.get("/api/v1/modeles")
def modeles() -> dict[str, object]:
    return {"modeles": lister_modeles()}


@app.get("/api/v1/categories")
def categories() -> dict[str, object]:
    return {"categories": categories_annee()}


@app.post("/api/v1/siret/verifier")
def verifier_siret(body: SiretBody) -> dict[str, object]:
    return {"siret": body.siret, "valide": siret_valide(body.siret)}


@app.post("/api/v1/dossiers")
def nouveau_dossier(body: Creation) -> dict[str, str]:
    try:
        return creer_dossier(body.modele, body.nom)
    except DossierError as exc:
        return {"erreur": str(exc)}


@app.get("/api/v1/dossier")
def lire_dossier(chemin: str = Query(min_length=1)) -> dict[str, object]:
    try:
        return lire_chemin(assurer_data(chemin))
    except DossierError as exc:
        return {"erreur": str(exc)}


@app.put("/api/v1/dossier")
def sauver_dossier(body: Enregistrement) -> dict[str, object]:
    try:
        if not body.chemin:
            raise DossierError("Le chemin du dossier est requis.")
        chemin = assurer_data(body.chemin)
        return enregistrer(chemin, body.dossier, body.mouvements)
    except DossierError as exc:
        return {"erreur": str(exc)}


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
        corps["dossier"] = body if "chemin" not in body else {"chemin": body["chemin"]}
        return corps
    except DossierError as exc:
        return {"erreur": str(exc)}
