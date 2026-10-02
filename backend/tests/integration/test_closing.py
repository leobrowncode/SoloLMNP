import base64
from uuid import uuid4

import pytest

from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_statements import book


@pytest.fixture
def client(seeded_client):  # noqa: F811
    for number, label in (("120000", "Résultat bénéfice"), ("129000", "Résultat perte")):
        assert (
            seeded_client.post(
                "/api/ledger/accounts",
                json={"number": number, "label": label, "account_type": "EQUITY"},
            ).status_code
            == 201
        )
    return seeded_client


def centralize(client, result):
    response = client.post(
        "/api/ledger/years/1/centralization",
        json={
            "request_id": str(uuid4()),
            "journal_code": "OD",
            "piece_reference": "CENT",
            "justification": "Centralisation confirmée pour la clôture de test.",
            "result_account": "120000" if not result.startswith("-") else "129000",
            "expected_result": result,
        },
    )
    assert response.status_code == 200, response.text


def test_close_reopen_fec_efi_and_documents(client, settings):
    book(client, "512000", "706000", "100.00")
    book(client, "615000", "401000", "40.00")
    centralize(client, "60.00")
    fiscal = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    assert fiscal.json()["declarable"] is False
    preview = client.get("/api/filing/years/1/precheck")
    assert preview.status_code == 200, preview.text
    assert preview.json()["blocking"] is False
    codes = [item["code"] for item in preview.json()["warnings"]]
    ready = client.post("/api/filing/years/1/ready", json={"acknowledged": codes})
    assert ready.status_code == 200, ready.text
    closed = client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 200, closed.text
    assert closed.json()["generation"] == 1
    first = client.get("/api/filing/years/1/fec")
    second = client.get("/api/filing/years/1/fec")
    assert first.status_code == 200
    assert first.content == second.content
    assert first.headers["x-content-sha256"] == second.headers["x-content-sha256"]
    assert b"JournalCode" in first.content
    assert b"\tCENT\t" not in first.content
    efi = client.get("/api/filing/years/1/efi").json()
    assert efi["transmission"] is False
    assert efi["personal_return"]["official_case"] is None
    assert efi["personal_return"]["separated_from_liasse"] is True
    package = client.get("/api/filing/years/1/package").json()
    assert package["declarable"] is False
    assert package["errors"] == []
    assert package["fields"][0]["entries"]
    reopened = client.post(
        "/api/filing/years/1/reopen",
        json={"confirmation": "ROUVRIR", "reason": "Correction motivée de test, sans suppression."},
    )
    assert reopened.status_code == 200, reopened.text
    assert client.get("/api/filing/years/1/fec").status_code == 409
    assert client.get("/api/filing/years/1/efi").status_code == 404
    document = client.post(
        "/api/filing/documents",
        json={
            "filename": "../piece.pdf",
            "media_type": "application/pdf",
            "content_base64": base64.b64encode(b"%PDF-1.4 test").decode(),
        },
    )
    assert document.status_code == 201, document.text
    assert document.json()["original_name"] == "piece.pdf"
    stored = list(settings.documents_dir.iterdir())
    assert len(stored) == 1
    assert stored[0].name.endswith(".pdf")
    assert ".." not in stored[0].name


def test_backup_round_trip_rejects_escape(client, settings):
    book(client, "512000", "706000", "10.00")
    created = client.post("/api/filing/backup")
    assert created.status_code == 201, created.text
    restored = client.post(
        "/api/filing/backup/restore", json={"filename": created.json()["filename"]}
    )
    assert restored.status_code == 200, restored.text
    escaped = client.post("/api/filing/backup/restore", json={"filename": "../sololmnp.sqlite3"})
    assert escaped.status_code == 422
