"""GET /api/dashboard for an empty, partial, blocked and ready-to-close dossier."""

import json
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app
from tests.integration.test_closing import centralize
from tests.integration.test_closing import client as closing_client  # noqa: F401
from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_statements import book


def _board(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/dashboard")
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    body = response.json()
    encoded = json.dumps(body, ensure_ascii=False).lower()
    assert "declarable" not in encoded
    assert "déclarable" not in encoded
    assert body["dossier"]["vintage_status"] == "research_only"
    assert body["continue"]["label"] == "Continuer"
    assert [step["id"] for step in body["steps"]] == [
        "structure",
        "operations",
        "assets",
        "opening",
        "closing",
        "filing",
    ]
    for step in body["steps"]:
        amount = step["amount_cents"]
        assert amount is None or isinstance(amount, int)
        assert isinstance(amount, bool) is False
    return body


def _step(body: dict[str, Any], step_id: str) -> dict[str, Any]:
    return next(step for step in body["steps"] if step["id"] == step_id)


def test_empty_dossier(settings, database) -> None:
    with TestClient(create_app(settings)) as client:
        body = _board(client)
    assert body["dossier"]["status"] == "incomplet"
    assert body["dossier"]["fiscal_year_id"] is None
    assert _step(body, "structure")["status"] == "a_faire"
    assert _step(body, "structure")["prerequisites"][0]["code"] == "NO_ACTIVITY"
    assert _step(body, "structure")["last_event"] is None
    assert body["continue"]["href"] == "/comptabilite/brouillons#creer-activite"
    assert all(step["status"] == "a_faire" for step in body["steps"])


def test_partial_dossier_is_missing_siren_and_a_property(seeded_client) -> None:  # noqa: F811
    body = _board(seeded_client)
    assert body["dossier"]["status"] == "incomplet"
    assert body["dossier"]["year"] == 2025
    assert body["dossier"]["year_status"] == "OPEN"
    structure = _step(body, "structure")
    assert structure["status"] == "en_cours"
    assert structure["prerequisites"][0]["code"] == "SIREN_REQUIRED"
    assert structure["prerequisites"][0]["action"]["href"] == (
        "/comptabilite/brouillons#identite-liasse"
    )
    assert structure["last_event"]["label"] in {"Activité créée", "Exercice 2025 créé"}
    assert structure["last_event"]["occurred_at"].endswith("Z")
    assert _step(body, "operations")["status"] == "a_faire"
    assert _step(body, "operations")["prerequisites"][0]["code"] == "NO_PROPERTY"
    assert _step(body, "opening")["status"] == "fait"
    assert _step(body, "closing")["status"] == "en_cours"
    assert _step(body, "filing")["status"] == "en_cours"
    assert body["continue"]["href"] == "/comptabilite/brouillons#identite-liasse"
    assert body["continue"]["step"] == "structure"


def test_blocked_dossier_after_calculation_without_siren(closing_client) -> None:  # noqa: F811
    book(closing_client, "512000", "706000", "100.00")
    created = closing_client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert created.status_code == 200, created.text
    body = _board(closing_client)
    assert body["dossier"]["status"] == "bloque"
    assert body["dossier"]["label"] == "Bloqué"
    assert any(step["status"] == "bloque" for step in body["steps"])
    filing = _step(body, "filing")
    assert filing["status"] == "bloque"
    assert filing["amount_cents"] is None or isinstance(filing["amount_cents"], int)
    codes = {item["code"] for item in filing["prerequisites"]}
    assert "SIREN_MANQUANT" in codes or "SIREN_REQUIRED" in codes
    assert body["continue"]["href"] == "/comptabilite/brouillons#identite-liasse"
    assert "Finale" not in filing["summary"] or body["dossier"]["year_status"] != "OPEN"


def test_ready_to_close_continues_to_the_precheck(closing_client) -> None:  # noqa: F811
    identity = closing_client.post("/api/ledger/activity/identity", json={"siren": "123456789"})
    assert identity.status_code == 200, identity.text
    book(closing_client, "512000", "706000", "100.00")
    book(closing_client, "615000", "401000", "40.00")
    centralize(closing_client, "60.00")
    fiscal = closing_client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    preview = closing_client.get("/api/filing/years/1/precheck")
    assert preview.status_code == 200, preview.text
    assert preview.json()["blocking"] is False
    codes = [item["code"] for item in preview.json()["warnings"]]
    ready = closing_client.post("/api/filing/years/1/ready", json={"acknowledged": codes})
    assert ready.status_code == 200, ready.text
    body = _board(closing_client)
    assert body["dossier"]["status"] == "pret_a_verifier"
    assert body["dossier"]["year_status"] == "READY_TO_CLOSE"
    assert _step(body, "closing")["status"] == "pret"
    assert _step(body, "closing")["last_event"]["label"] == "Exercice passé en prêt à clôturer"
    assert body["continue"]["step"] == "closing"
    assert body["continue"]["href"] == "/fiscalite#close-title"
    assert body["continue"]["detail"] == "Prochaine action : confirmer la clôture."
    filing = _step(body, "filing")
    assert filing["status"] == "pret"
    assert "Bloquée" in filing["summary"] or "Provisoire" in filing["summary"]
    assert "recherche" in filing["summary"].lower()
