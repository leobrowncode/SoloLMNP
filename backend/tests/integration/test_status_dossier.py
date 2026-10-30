"""GET /api/status exposes the business dossier, never a déclarable vintage."""

import json
from typing import Any

from tests.integration.test_closing import centralize
from tests.integration.test_closing import client as closing_client  # noqa: F401
from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_statements import book

VALIDATED: dict[str, Any] = {
    "vintage": "2025",
    "version": "validation-1",
    "status": "validated",
    "declarable": True,
    "official_source": {
        "reference": "CERFA 2031-SD et liasse 2033-SD, millésime 2025",
        "url": "https://www.impots.gouv.fr/formulaire/2031-sd/impot-sur-le-revenu",
    },
    "validated_on": "2026-10-02",
    "scope": {
        "activity": "LMNP déclaré",
        "regime": "réel simplifié BIC",
        "excluded": ["cession", "TVA", "plus-values", "LMP"],
    },
    "rules_version": "research-1",
}


def _dossier(client) -> dict[str, Any]:
    response = client.get("/api/status")
    assert response.status_code == 200, response.text
    body = response.json()
    dossier = body["dossier"]
    assert body["fiscal"]["status"] == "research_only"
    assert dossier["vintage_status"] == "research_only"
    encoded = json.dumps(dossier)
    assert "declarable" not in encoded
    assert "Déclarable" not in encoded
    return dossier


def _identify(client) -> None:
    identity = client.post("/api/ledger/activity/identity", json={"siren": "123456789"})
    assert identity.status_code == 200, identity.text


def test_seeded_year_without_a_calculation_is_incomplete(seeded_client):  # noqa: F811
    dossier = _dossier(seeded_client)
    assert dossier["status"] == "incomplet"
    assert dossier["label"] == "Incomplet"
    assert dossier["year"] == 2025
    assert dossier["year_status"] == "OPEN"


def test_missing_siren_blocks_the_dossier_after_calculation(closing_client):  # noqa: F811
    book(closing_client, "512000", "706000", "100.00")
    created = closing_client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert created.status_code == 200, created.text
    dossier = _dossier(closing_client)
    assert dossier["status"] == "bloque"
    assert dossier["label"] == "Bloqué"


def test_research_sheet_is_ready_to_review(closing_client):  # noqa: F811
    _identify(closing_client)
    book(closing_client, "512000", "706000", "100.00")
    book(closing_client, "615000", "401000", "40.00")
    created = closing_client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert created.status_code == 200, created.text
    dossier = _dossier(closing_client)
    assert dossier["status"] == "pret_a_verifier"
    assert dossier["label"] == "Prêt à vérifier"
    assert dossier["year_status"] == "OPEN"


def test_closed_research_year_is_cloture(closing_client):  # noqa: F811
    _identify(closing_client)
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
    assert _dossier(closing_client)["status"] == "pret_a_verifier"
    closed = closing_client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 200, closed.text
    dossier = _dossier(closing_client)
    assert dossier["status"] == "cloture"
    assert dossier["label"] == "Clôturé"
    assert dossier["year_status"] == "CLOSED"


def test_declarable_trust_does_not_change_the_dossier_label(closing_client, monkeypatch):  # noqa: F811
    def _load(vintage: str) -> dict[str, Any]:
        if vintage == "2025":
            return json.loads(json.dumps(VALIDATED))
        return {"vintage": vintage, "status": "research_only", "declarable": False}

    monkeypatch.setattr("app.domain.fiscal.output_status.load_validation", _load)
    _identify(closing_client)
    book(closing_client, "512000", "706000", "100.00")
    book(closing_client, "615000", "401000", "40.00")
    created = closing_client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert created.status_code == 200, created.text
    assert created.json()["output_status"] == "declarable"
    dossier = _dossier(closing_client)
    assert dossier["status"] == "pret_a_verifier"
    assert dossier["label"] == "Prêt à vérifier"
    assert dossier["vintage_status"] == "research_only"
