from pathlib import Path

from fastapi.testclient import TestClient

from lmnp_core.api import app

GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "premier-exercice" / "input"


def test_health_and_build() -> None:
    client = TestClient(app)
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    built = client.post("/api/v1/build", json={"chemin": str(GOLDEN)})
    assert built.status_code == 200
    body = built.json()
    assert body["annees"]["2025"]["resultat_fiscal"] == 353518
    assert body["etat"]["effectif"] == "brouillon"
    refused = client.post("/api/v1/build", json={"regime": "lmp", "nom": "x"})
    assert "erreur" in refused.json()


def test_persist_endpoints() -> None:
    client = TestClient(app)
    modeles = client.get("/api/v1/modeles")
    assert modeles.status_code == 200
    assert modeles.json()["modeles"]
    lu = client.get("/api/v1/dossier", params={"chemin": str(GOLDEN)})
    assert lu.status_code == 200
    assert lu.json()["dossier"]["siret"] == "12345678900017"
    siret = client.post("/api/v1/siret/verifier", json={"siret": "12345678900015"})
    assert siret.json()["valide"] is True
