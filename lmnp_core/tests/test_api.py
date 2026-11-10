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
