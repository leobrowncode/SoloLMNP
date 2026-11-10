from pathlib import Path

from app.core.config import Settings
from fastapi.testclient import TestClient

from lmnp_core.api import creer_app
from lmnp_core.depot import DepotFichiers


def _client(tmp_path: Path) -> TestClient:
    reglages = Settings(
        _env_file=None,
        app_env="development",
        auth_mode="local",
        allowed_hosts=("testserver", "localhost", "127.0.0.1"),
    )
    return TestClient(creer_app(DepotFichiers(tmp_path), reglages))


def test_health_build_and_forbidden_path(tmp_path: Path) -> None:
    client = _client(tmp_path)
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    created = client.post("/api/v1/dossiers", json={"modele": "premier-exercice"})
    assert created.status_code == 200
    assert "erreur" not in created.json()
    built = client.post("/api/v1/build", json={})
    assert built.status_code == 200
    body = built.json()
    assert body["annees"]["2025"]["resultat_fiscal"] == 353518
    assert body["etat"]["effectif"] == "brouillon"
    assert body["telechargements"]
    fec = client.get("/api/v1/sorties/" + body["sorties"]["fec"]["nom"])
    assert fec.status_code == 200
    assert fec.content.startswith(b"JournalCode")
    archive = next(item for item in body["telechargements"] if item["nom"].endswith(".zip"))
    zip_response = client.get(archive["url"])
    assert zip_response.status_code == 200
    assert zip_response.content.startswith(b"PK")
    refused = client.post("/api/v1/build", json={"regime": "lmp", "nom": "x"})
    assert "erreur" in refused.json()
    blocked = client.post("/api/v1/build", json={"chemin": "/etc"})
    assert "chemin" in blocked.json()["erreur"]


def test_persist_endpoints(tmp_path: Path) -> None:
    client = _client(tmp_path)
    modeles = client.get("/api/v1/modeles")
    assert modeles.status_code == 200
    assert modeles.json()["modeles"]
    assert "chemin" not in modeles.json()["modeles"][0]
    vide = client.get("/api/v1/dossier")
    assert vide.status_code == 404
    lu = client.get("/api/v1/modeles/premier-exercice")
    assert lu.status_code == 200
    assert lu.json()["dossier"]["siret"] == "12345678900017"
    siret = client.post("/api/v1/siret/verifier", json={"siret": "12345678900015"})
    assert siret.json()["valide"] is True
