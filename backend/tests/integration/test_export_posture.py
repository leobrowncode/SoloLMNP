"""Downloads follow exports.*.posture: before calculation, before close, blocked, final."""

import json
from typing import Any

import pytest

from app.core.config import PROJECT_ROOT
from tests.integration.test_closing import centralize
from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_statements import book


@pytest.fixture
def client(seeded_client):  # noqa: F811
    return seeded_client


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
    "rules_version": "research-2",
}


def test_before_calculation_blocks_liasse_and_fec(client):
    status = client.get("/api/filing/years/1/exports")
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["produced"] is False
    for kind in ("liasse", "pdf", "fec", "archive"):
        assert body["exports"][kind]["posture"] == "bloquee"
        assert body["exports"][kind]["label"] == "Bloquée"
        assert body["exports"][kind]["download"] is False
    codes = {item["code"] for item in body["prerequisites"]}
    assert "FISCAL_NOT_COMPUTED" in codes
    assert "YEAR_NOT_CLOSED" in codes

    pdf = client.get("/api/filing/years/1/efi.pdf")
    assert pdf.status_code == 409
    assert pdf.json()["detail"]["code"] == "FISCAL_NOT_COMPUTED"
    assert pdf.json()["detail"]["action"]["href"].startswith("/fiscalite")
    fec = client.get("/api/filing/years/1/fec")
    assert fec.status_code == 409
    assert fec.json()["detail"]["code"] == "YEAR_NOT_CLOSED"
    assert "clôturé" in fec.json()["detail"]["message"]
    assert fec.json()["detail"]["action"]["label"]
    archive = client.get("/api/filing/years/1/archive")
    assert archive.status_code == 409
    assert archive.json()["detail"]["code"] == "YEAR_NOT_CLOSED"
    assert client.get("/api/filing/years/1/efi").status_code == 404


def test_before_close_allows_provisional_pdf_and_blocks_final_fec(client):
    _identify(client)
    book(client, "512000", "706000", "100.00")
    book(client, "615000", "401000", "40.00")
    assert client.post("/api/fiscal/years/1", json={"adjustments": []}).status_code == 200

    status = client.get("/api/filing/years/1/exports").json()
    assert status["exports"]["liasse"]["posture"] == "provisoire"
    assert status["exports"]["pdf"]["download"] is True
    assert status["exports"]["fec"]["posture"] == "bloquee"
    assert status["exports"]["archive"]["download"] is False
    assert any(item["code"] == "YEAR_NOT_CLOSED" for item in status["prerequisites"])

    pdf = client.get("/api/filing/years/1/efi.pdf")
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["x-export-posture"] == "provisoire"
    assert "Posture d’export : Provisoire.".encode("cp1252") in pdf.content
    assert b"pr\xeate \xe0 recopier" not in pdf.content.lower()
    fec = client.get("/api/filing/years/1/fec")
    assert fec.status_code == 409
    assert fec.json()["detail"]["code"] == "YEAR_NOT_CLOSED"


def test_blocked_liasse_lists_the_missing_siren_before_download(client):
    book(client, "512000", "706000", "100.00")
    assert client.post("/api/fiscal/years/1", json={"adjustments": []}).status_code == 200
    status = client.get("/api/filing/years/1/exports").json()
    assert status["exports"]["liasse"]["posture"] == "bloquee"
    assert status["exports"]["pdf"]["download"] is False
    siren = next(item for item in status["prerequisites"] if item["code"] == "SIREN_MANQUANT")
    assert "SIREN" in siren["message"]
    assert siren["action"]["href"].endswith("#identite-liasse")
    pdf = client.get("/api/filing/years/1/efi.pdf")
    assert pdf.status_code == 409
    assert pdf.json()["detail"]["code"] == "SIREN_MANQUANT"
    assert pdf.json()["detail"]["action"]["href"] == siren["action"]["href"]


def test_closed_research_year_keeps_provisional_liasse_and_final_fec(client, monkeypatch):
    _close(client)
    status = client.get("/api/filing/years/1/exports").json()
    assert status["output_status"] == "recherche"
    assert status["exports"]["liasse"]["posture"] == "provisoire"
    assert status["exports"]["pdf"]["label"] == "Provisoire"
    assert status["exports"]["fec"]["posture"] == "finale"
    assert status["exports"]["archive"]["download"] is True
    stored = json.loads((PROJECT_ROOT / "fiscal" / "2025" / "validation.json").read_text())
    assert stored["status"] == "research_only"
    assert stored["declarable"] is False

    fec = client.get("/api/filing/years/1/fec")
    assert fec.status_code == 200, fec.text
    assert fec.headers["x-export-posture"] == "finale"
    archive = client.get("/api/filing/years/1/archive")
    assert archive.status_code == 200, archive.text
    assert archive.headers["x-export-posture"] == "finale"
    pdf = client.get("/api/filing/years/1/efi.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["x-export-posture"] == "provisoire"

    def _validated(vintage: str) -> dict[str, Any]:
        assert vintage == "2025"
        return VALIDATED

    monkeypatch.setattr("app.domain.fiscal.output_status.load_validation", _validated)
    final = client.get("/api/filing/years/1/exports").json()
    assert final["output_status"] == "declarable"
    assert final["exports"]["liasse"]["posture"] == "finale"
    assert final["exports"]["pdf"]["download"] is True
    assert final["exports"]["fec"]["posture"] == "finale"
    ready = client.get("/api/filing/years/1/efi.pdf")
    assert ready.status_code == 200
    assert ready.headers["x-export-posture"] == "finale"
    assert "Posture d’export : Finale.".encode("cp1252") in ready.content
    on_disk = json.loads((PROJECT_ROOT / "fiscal" / "2025" / "validation.json").read_text())
    assert on_disk["status"] == "research_only"


def _identify(client) -> None:
    assert (
        client.post("/api/ledger/activity/identity", json={"siren": "123456789"}).status_code == 200
    )


def _close(client) -> None:
    for number, label in (("120000", "Résultat bénéfice"), ("129000", "Résultat perte")):
        assert (
            client.post(
                "/api/ledger/accounts",
                json={"number": number, "label": label, "account_type": "EQUITY"},
            ).status_code
            == 201
        )
    _identify(client)
    book(client, "512000", "706000", "100.00")
    book(client, "615000", "401000", "40.00")
    centralize(client, "60.00")
    assert client.post("/api/fiscal/years/1", json={"adjustments": []}).status_code == 200
    preview = client.get("/api/filing/years/1/precheck")
    assert preview.status_code == 200, preview.text
    assert preview.json()["blocking"] is False, preview.text
    codes = [item["code"] for item in preview.json()["warnings"]]
    assert client.post("/api/filing/years/1/ready", json={"acknowledged": codes}).status_code == 200
    closed = client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 200, closed.text
