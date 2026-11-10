"""Routes `/api/v1`. Le owner vient de la session, jamais d'un chemin envoyé par le client."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from lmnp_core.build import build_dossier
from lmnp_core.depot import Depot, DepotAbsent, DepotError, relatif_sur, type_mime
from lmnp_core.dossier import DossierError, dossier_from_mapping
from lmnp_core.persist import (
    categories_annee,
    copier_modele,
    enregistrer_owner,
    enregistrer_sorties,
    lire_modele,
    lire_owner,
    lister_modeles,
    materialiser,
)
from lmnp_core.siret import valide as siret_valide
from lmnp_core.sorties import pour_api, produire

_TAILLE_MAX = 10 * 1024 * 1024
_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".csv"}
_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class Creation(BaseModel):
    modele: str = Field(min_length=1, pattern=r"^[a-z0-9-]+$")


class Enregistrement(BaseModel):
    dossier: dict[str, Any]
    mouvements: list[dict[str, Any]] | None = None


class SiretBody(BaseModel):
    siret: str = Field(min_length=14, max_length=14)


def routeur_v1(depot: Depot) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/modeles")
    def modeles() -> dict[str, object]:
        return {
            "modeles": [
                {"id": item["id"], "etiquette": item["etiquette"]} for item in lister_modeles()
            ]
        }

    @router.get("/api/v1/modeles/{cle}")
    def modele(cle: str) -> dict[str, object]:
        try:
            return lire_modele(cle)
        except DossierError as exc:
            return {"erreur": str(exc)}

    @router.get("/api/v1/categories")
    def categories() -> dict[str, object]:
        return {"categories": categories_annee()}

    @router.post("/api/v1/siret/verifier")
    def verifier_siret(body: SiretBody) -> dict[str, object]:
        return {"siret": body.siret, "valide": siret_valide(body.siret)}

    @router.post("/api/v1/dossiers")
    def nouveau_dossier(body: Creation, request: Request) -> dict[str, object]:
        try:
            return copier_modele(depot, _owner(request), body.modele)
        except DossierError as exc:
            return {"erreur": str(exc)}

    @router.get("/api/v1/dossier", response_model=None)
    def lire_dossier(request: Request) -> dict[str, object] | JSONResponse:
        try:
            return lire_owner(depot, _owner(request))
        except DossierError as exc:
            if str(exc).startswith("Aucun dossier"):
                return JSONResponse(status_code=404, content={"erreur": str(exc)})
            return {"erreur": str(exc)}

    @router.put("/api/v1/dossier")
    def sauver_dossier(body: Enregistrement, request: Request) -> dict[str, object]:
        try:
            return enregistrer_owner(depot, _owner(request), body.dossier, body.mouvements)
        except DossierError as exc:
            return {"erreur": str(exc)}

    @router.post("/api/v1/build")
    def build_endpoint(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            if body and "chemin" in body:
                raise DossierError("Le chemin local n'est pas accepté.")
            owner = _owner(request)
            if body and "regime" in body:
                resultat = build_dossier(dossier_from_mapping(body))
                produit = produire(resultat)
                corps = resultat.to_json()
                corps["sorties"] = pour_api(produit)
                return corps
            lu = lire_owner(depot, owner)
            mapping = materialiser(lu["dossier"], depot, owner)
            resultat = build_dossier(dossier_from_mapping(mapping))
            produit = produire(resultat)
            noms = enregistrer_sorties(depot, owner, produit)
            corps = resultat.to_json()
            corps["sorties"] = pour_api(produit)
            corps["telechargements"] = [
                {"nom": nom, "url": f"/api/v1/sorties/{nom}"} for nom in noms
            ]
            return corps
        except DossierError as exc:
            return {"erreur": str(exc)}

    @router.get("/api/v1/sorties/{nom}", response_model=None)
    def telecharger_sortie(nom: str, request: Request) -> Response:
        return _fichier(depot, _owner(request), f"sorties/{nom}", nom)

    @router.get("/api/v1/justificatifs")
    def lister_justificatifs(request: Request) -> dict[str, object]:
        noms = [
            chemin.removeprefix("justificatifs/")
            for chemin in depot.lister(_owner(request), "justificatifs")
            if chemin.startswith("justificatifs/")
        ]
        return {"noms": noms}

    @router.put("/api/v1/justificatifs/{nom}")
    async def deposer_justificatif(nom: str, request: Request) -> dict[str, object]:
        try:
            propre = _nom_justificatif(nom)
            contenu = await request.body()
        except DepotError as exc:
            return {"erreur": str(exc)}
        if len(contenu) > _TAILLE_MAX:
            return {"erreur": "Justificatif trop lourd (10 Mo maximum)."}
        if not contenu:
            return {"erreur": "Justificatif vide."}
        depot.ecrire(_owner(request), f"justificatifs/{propre}", contenu)
        return {"nom": propre}

    @router.get("/api/v1/justificatifs/{nom}", response_model=None)
    def lire_justificatif(nom: str, request: Request) -> Response:
        try:
            propre = _nom_justificatif(nom)
        except DepotError as exc:
            return JSONResponse(
                status_code=400,
                content={"detail": {"code": "INVALID_DOCUMENT", "message": str(exc)}},
            )
        return _fichier(depot, _owner(request), f"justificatifs/{propre}", propre)

    return router


def inclure_v1(application: FastAPI, depot: Depot) -> None:
    if getattr(application.state, "v1_inclus", False):
        return
    application.include_router(routeur_v1(depot))
    application.state.v1_inclus = True


def _owner(request: Request) -> str:
    principal = getattr(request.state, "principal", None)
    subject = getattr(principal, "subject", None)
    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHENTICATED", "message": "Connectez-vous pour continuer."},
        )
    return subject.strip()


def _fichier(depot: Depot, owner: str, relatif: str, nom: str) -> Response:
    try:
        relatif_sur(relatif)
        contenu = depot.lire(owner, relatif)
    except (DepotError, DepotAbsent):
        return JSONResponse(
            status_code=404,
            content={"detail": {"code": "NOT_FOUND", "message": "Fichier introuvable."}},
        )
    return Response(
        content=contenu,
        media_type=type_mime(nom),
        headers={
            "Content-Disposition": f'attachment; filename="{Path(nom).name}"',
            "Cache-Control": "no-store",
        },
    )


def _nom_justificatif(nom: str) -> str:
    nettoye = re.sub(r"[^A-Za-z0-9._-]", "-", Path(nom).name).strip(".-")
    suffixe = Path(nettoye).suffix.lower()
    if not nettoye or suffixe not in _EXTENSIONS or not _SEGMENT.fullmatch(nettoye):
        raise DepotError("Nom de justificatif refusé.")
    return nettoye
