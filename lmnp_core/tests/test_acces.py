"""Isolation, liste d'adresses, mode local refusé en production."""

from pathlib import Path

import pytest
from app.core.auth import OTHER_EMAIL, OTHER_SUBJECT, TEST_EMAIL, TEST_SECRET, issue_test_token
from app.core.config import Settings
from fastapi.testclient import TestClient

from lmnp_core.api import creer_app
from lmnp_core.depot import DepotBlob, DepotFichiers


def _reglages() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        auth_mode="test",
        auth_test_secret=TEST_SECRET,
        allowed_emails=(TEST_EMAIL, OTHER_EMAIL),
        allowed_hosts=("testserver", "localhost", "127.0.0.1"),
    )


def _bearer(email: str, subject: str) -> dict[str, str]:
    token = issue_test_token(TEST_SECRET, email=email, subject=subject)
    return {"Authorization": "Bearer " + token}


def test_deux_comptes_ne_voient_pas_le_meme_dossier(tmp_path: Path) -> None:
    client = TestClient(creer_app(DepotFichiers(tmp_path), _reglages()))
    ada = _bearer(TEST_EMAIL, "ada")
    bea = _bearer(OTHER_EMAIL, OTHER_SUBJECT)
    cree = client.post("/api/v1/dossiers", json={"modele": "premier-exercice"}, headers=ada)
    assert cree.status_code == 200
    lu = client.get("/api/v1/dossier", headers=ada).json()
    lu["dossier"]["nom"] = "Dossier Ada"
    sauve = client.put(
        "/api/v1/dossier",
        json={"dossier": lu["dossier"], "mouvements": lu["mouvements"]},
        headers=ada,
    )
    assert sauve.status_code == 200
    assert sauve.json()["dossier"]["nom"] == "Dossier Ada"
    autre = client.post("/api/v1/dossiers", json={"modele": "plafond-39c"}, headers=bea)
    assert autre.status_code == 200
    assert client.get("/api/v1/dossier", headers=ada).json()["dossier"]["nom"] == "Dossier Ada"
    assert client.get("/api/v1/dossier", headers=bea).json()["dossier"]["nom"] != "Dossier Ada"
    depose = client.put(
        "/api/v1/justificatifs/quittance.pdf",
        content=b"%PDF-ada",
        headers={**ada, "content-type": "application/pdf"},
    )
    assert depose.status_code == 200
    assert client.get("/api/v1/justificatifs", headers=bea).json()["noms"] == []
    assert client.get("/api/v1/justificatifs/quittance.pdf", headers=ada).content == b"%PDF-ada"
    assert client.get("/api/v1/justificatifs/quittance.pdf", headers=bea).status_code == 404


def test_email_hors_liste_refuse(tmp_path: Path) -> None:
    client = TestClient(creer_app(DepotFichiers(tmp_path), _reglages()))
    intrus = _bearer("intrus@example.com", "intrus")
    response = client.get("/api/v1/dossier", headers=intrus)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "EMAIL_NOT_ALLOWED"
    admission = client.get("/api/auth/admission", params={"email": "intrus@example.com"})
    assert admission.status_code == 403
    assert admission.json()["detail"]["code"] == "EMAIL_NOT_ALLOWED"
    assert client.get("/api/v1/dossier", headers=_bearer(TEST_EMAIL, "ada")).status_code == 404


def test_blob_faux_client_isole_deux_comptes() -> None:
    class Faux:
        def __init__(self) -> None:
            self.objets: dict[str, bytes] = {}

        def put(self, pathname: str, content: bytes, content_type: str, *, overwrite: bool) -> None:
            del content_type, overwrite
            self.objets[pathname] = content

        def get(self, pathname: str) -> bytes:
            if pathname not in self.objets:
                raise FileNotFoundError(pathname)
            return self.objets[pathname]

        def list_pathnames(self, prefix: str) -> list[str]:
            return [nom for nom in self.objets if nom.startswith(prefix)]

    faux = Faux()
    client = TestClient(creer_app(DepotBlob(faux), _reglages()))
    ada = _bearer(TEST_EMAIL, "ada")
    bea = _bearer(OTHER_EMAIL, OTHER_SUBJECT)
    cree = client.post("/api/v1/dossiers", json={"modele": "premier-exercice"}, headers=ada)
    assert cree.status_code == 200
    assert any(cle.startswith("v1/ada/") for cle in faux.objets)
    assert not any(cle.startswith("v1/" + OTHER_SUBJECT) for cle in faux.objets)
    assert client.get("/api/v1/dossier", headers=bea).status_code == 404
    assert client.get("/api/v1/dossier", headers=ada).json()["dossier"]["siret"] == "12345678900017"


def test_mode_local_refuse_en_production(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_MODE", "local")
    with pytest.raises(RuntimeError, match="AUTH_MODE=local"):
        creer_app(DepotFichiers(tmp_path))


def test_mode_local_refuse_sur_vercel(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "local")
    with pytest.raises(RuntimeError, match="AUTH_MODE=local"):
        creer_app(DepotFichiers(tmp_path))
