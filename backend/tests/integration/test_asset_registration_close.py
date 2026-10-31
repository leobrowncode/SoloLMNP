"""Audit path: no depreciation and no close while the asset is off the balance sheet."""

from uuid import uuid4

import pytest

from tests.integration.test_assets import client as assets_client  # noqa: F401
from tests.integration.test_assets import furniture
from tests.integration.test_statements import book


@pytest.fixture
def client(assets_client):  # noqa: F811
    return assets_client


def _opened_furniture() -> dict[str, object]:
    return furniture(acquisition_date="2025-01-01", service_start_date="2025-01-01")


def _equity(client, number: str, label: str) -> None:
    assert (
        client.post(
            "/api/ledger/accounts",
            json={"number": number, "label": label, "account_type": "EQUITY"},
        ).status_code
        == 201
    )


def _centralize(client, result: str) -> None:
    account = "129000" if result.startswith("-") else "120000"
    response = client.post(
        "/api/ledger/years/1/centralization",
        json={
            "request_id": str(uuid4()),
            "journal_code": "OD",
            "piece_reference": "CENT-IMMO",
            "justification": "Centralisation de test avant le contrôle des immobilisations.",
            "result_account": account,
            "expected_result": result,
        },
    )
    assert response.status_code == 200, response.text


def _enter(client, **extra: object) -> None:
    payload = {
        "fiscal_year_id": 1,
        "loans": [],
        "bank_amount": "0.00",
        "prior_charges": [],
        "piece_reference": "ACTE-2025",
        "confirm": True,
    }
    payload.update(extra)
    response = client.post("/api/assets/properties/1/entry", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["posted"] is True


def test_depreciation_is_refused_until_the_property_enters_the_books(client):
    assert client.post("/api/assets", json=_opened_furniture()).status_code == 201
    period = client.post("/api/assets/years/1/calculate").json()[0]
    refused = client.post(
        f"/api/assets/periods/{period['id']}/post",
        json={"request_id": "dotation-sans-bien", "piece_reference": "DOT-REFUS"},
    )
    assert refused.status_code == 409, refused.text
    detail = refused.json()["detail"]
    assert detail["code"] == "ASSET_NOT_BOOKED"
    assert "entrer" in detail["message"]
    assert detail["action"]["href"] == "/immobilisations#entree-bien"
    assert detail["action"]["label"] == "Faire entrer le bien en comptabilité"

    _enter(client)
    posted = client.post(
        f"/api/assets/periods/{period['id']}/post",
        json={"request_id": "dotation-apres-entree", "piece_reference": "DOT-2025"},
    )
    assert posted.status_code == 201, posted.text

    result = client.get("/api/ledger/years/1/statements").json()["income_statement"]["result"]
    _equity(client, "120000", "Résultat bénéfice")
    _equity(client, "129000", "Résultat perte")
    _centralize(client, result)
    assert client.post("/api/fiscal/years/1", json={"adjustments": []}).status_code == 200
    identity = client.post("/api/ledger/activity/identity", json={"siren": "123456789"})
    assert identity.status_code == 200, identity.text
    precheck = client.get("/api/filing/years/1/precheck").json()
    errors = [item["code"] for item in precheck["errors"]]
    assert "IMMOBILISATIONS_ECART" not in errors
    assert "IMMOBILISATIONS_NETTES_NEGATIVES" not in errors
    assert precheck["blocking"] is False, precheck
    warnings = [item["code"] for item in precheck["warnings"]]
    ready = client.post("/api/filing/years/1/ready", json={"acknowledged": warnings})
    assert ready.status_code == 200, ready.text
    closed = client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 200, closed.text
    sheet = client.get("/api/filing/years/1/efi").json()
    by_case = {field["official_case"]: field["value"] for field in sheet["liasse"]["fields"]}
    assert not by_case.get("030", "0.00").startswith("-")
    assert "IMMOBILISATIONS_ECART" not in {item["code"] for item in sheet["blocking"]}
    assert "IMMOBILISATIONS_NETTES_NEGATIVES" not in {item["code"] for item in sheet["blocking"]}


def test_gap_and_negative_box_030_block_close_and_cannot_be_acknowledged(client):
    assert client.post("/api/assets", json=_opened_furniture()).status_code == 201
    book(client, "681100", "281840", "100.00")
    _equity(client, "129000", "Résultat perte")
    _centralize(client, "-100.00")
    assert client.post("/api/fiscal/years/1", json={"adjustments": []}).status_code == 200
    precheck = client.get("/api/filing/years/1/precheck").json()
    errors = [item["code"] for item in precheck["errors"]]
    warnings = [item["code"] for item in precheck["warnings"]]
    assert "IMMOBILISATIONS_ECART" in errors
    assert "IMMOBILISATIONS_NETTES_NEGATIVES" in errors
    assert "IMMOBILISATIONS_ECART" not in warnings
    assert "IMMOBILISATIONS_NETTES_NEGATIVES" not in warnings
    assert precheck["blocking"] is True
    acknowledged = client.post(
        "/api/filing/years/1/ready",
        json={
            "acknowledged": [
                *warnings,
                "IMMOBILISATIONS_ECART",
                "IMMOBILISATIONS_NETTES_NEGATIVES",
            ]
        },
    )
    assert acknowledged.status_code == 409
    assert acknowledged.json()["detail"]["code"] == "CLOSE_BLOCKED"
    closed = client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 409
    sheet = client.get("/api/filing/years/1/efi").json()
    box = next(field for field in sheet["liasse"]["fields"] if field["official_case"] == "030")
    assert box["value"].startswith("-")


def test_entries_after_centralization_ask_for_a_new_centralization(client):
    book(client, "512000", "706000", "100.00")
    _equity(client, "120000", "Résultat bénéfice")
    _centralize(client, "100.00")
    assert client.post("/api/assets", json=_opened_furniture()).status_code == 201
    _enter(
        client,
        prior_charges=[
            {
                "account_number": "661000",
                "amount": "1200.00",
                "label": "Intérêts payés avant la mise en location",
            },
            {
                "account_number": "627000",
                "amount": "500.00",
                "label": "Frais de dossier",
            },
        ],
    )
    preview = client.get("/api/ledger/years/1/centralization-preview").json()
    assert preview["recentralization_required"] is True
    assert "recentralis" in preview["recentralization_message"]
    precheck = client.get("/api/filing/years/1/precheck").json()
    assert "CENTRALIZATION_STALE" in [item["code"] for item in precheck["errors"]]
    appropriation = client.post(
        "/api/ledger/years/1/appropriation",
        json={
            "request_id": str(uuid4()),
            "journal_code": "OD",
            "piece_reference": "AFF-STALE",
            "justification": "Affectation refusée tant que le résultat a bougé.",
            "source_account": "120000",
            "target_account": "108000",
            "expected_amount": "100.00",
        },
    )
    assert appropriation.status_code == 409, appropriation.text
    assert appropriation.json()["detail"]["code"] == "CENTRALIZATION_STALE"
