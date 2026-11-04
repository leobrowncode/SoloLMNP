"""Two accounts never read or rewrite each other's dossier."""

import base64

import pytest
from fastapi.testclient import TestClient

from app.core.auth import OTHER_EMAIL, OTHER_SUBJECT, TEST_SECRET, issue_test_token
from app.core.config import Settings
from app.core.database import Database
from app.main import create_app

_WRITE = {"X-SoloLMNP-Request": "1"}
PDF = b"%PDF-1.4 secret"


def _client(settings: Settings, subject: str, email: str) -> TestClient:
    token = issue_test_token(TEST_SECRET, email=email, subject=subject)
    return TestClient(
        create_app(settings),
        headers={"Authorization": "Bearer " + token, **_WRITE},
    )


def _year(client: TestClient, name: str) -> int:
    activity = client.post(
        "/api/ledger/activity",
        json={"activity_name": name, "activity_start_date": "2025-01-01"},
    )
    assert activity.status_code == 201, activity.text
    year = client.post(
        "/api/ledger/years",
        json={
            "year": 2025,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "fiscal_vintage": "2025",
        },
    )
    assert year.status_code == 201, year.text
    created = year.json()["years"]
    return int(created[0]["id"])


def _entry(client: TestClient, year_id: int, label: str) -> dict[str, object]:
    created = client.post(
        "/api/ledger/entries",
        json={
            "fiscal_year_id": year_id,
            "journal_code": "BQ",
            "accounting_date": "2025-02-01",
            "piece_reference": "ISO-001",
            "piece_date": "2025-02-01",
            "label": label,
            "lines": [
                {
                    "account_number": "512000",
                    "label": "Banque",
                    "debit": "10.00",
                    "credit": "0.00",
                },
                {
                    "account_number": "706000",
                    "label": "Produit",
                    "debit": "0.00",
                    "credit": "10.00",
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_missing_token_and_unknown_email(settings: Settings, database: Database) -> None:
    del database
    with TestClient(create_app(settings), headers={"Authorization": "Bearer non"}) as client:
        assert client.get("/api/health").status_code == 200
        denied = client.get("/api/status")
        assert denied.status_code == 401
        assert denied.json()["detail"]["code"] == "INVALID_TOKEN"
        assert client.get("/api/filing/documents/1/content").status_code == 401
        assert client.get("/api/filing/dossier/exports").status_code == 401
    outsider = issue_test_token(TEST_SECRET, email="intrus@example.com", subject="intrus")
    with TestClient(
        create_app(settings), headers={"Authorization": "Bearer " + outsider, **_WRITE}
    ) as client:
        refused = client.get("/api/status")
        assert refused.status_code == 403
        assert refused.json()["detail"]["code"] == "EMAIL_NOT_ALLOWED"


def test_user_b_cannot_read_or_change_user_a(settings: Settings, database: Database) -> None:
    del database
    ada = _client(settings, "test-ada", "ada@sololmnp.test")
    year_id = _year(ada, "Ada")
    entry = _entry(ada, year_id, "Loyer secret")
    document = ada.post(
        "/api/filing/documents",
        json={
            "filename": "secret.pdf",
            "media_type": "application/pdf",
            "content_base64": base64.b64encode(PDF).decode(),
        },
    )
    assert document.status_code == 201, document.text
    document_id = document.json()["id"]
    exported = ada.post("/api/filing/dossier/export")
    assert exported.status_code == 201, exported.text
    filename = exported.json()["filename"]

    bea = _client(settings, OTHER_SUBJECT, OTHER_EMAIL)
    assert bea.get("/api/ledger/setup").json()["activity"] is None
    assert bea.get(f"/api/ledger/years/{year_id}/balance").status_code == 404
    assert bea.get(f"/api/filing/documents/{document_id}/content").status_code == 404
    assert bea.get("/api/filing/documents").json()["documents"] == []
    assert bea.delete(f"/api/filing/documents/{document_id}").status_code == 404
    assert bea.get("/api/filing/dossier/exports").json()["backups"] == []
    assert (
        bea.post("/api/filing/dossier/exports/verify", json={"filename": filename}).status_code
        == 404
    )
    assert (
        bea.post(
            "/api/filing/dossier/restore",
            json={"filename": filename, "confirmation": "RESTAURER"},
        ).status_code
        == 404
    )
    edited = bea.put(
        f"/api/ledger/entries/{entry['id']}",
        json={
            "fiscal_year_id": year_id,
            "journal_code": "BQ",
            "accounting_date": "2025-02-01",
            "piece_reference": "ISO-001",
            "piece_date": "2025-02-01",
            "label": "Piraté",
            "expected_version": 1,
            "lines": [
                {
                    "account_number": "512000",
                    "label": "Banque",
                    "debit": "10.00",
                    "credit": "0.00",
                },
                {
                    "account_number": "706000",
                    "label": "Produit",
                    "debit": "0.00",
                    "credit": "10.00",
                },
            ],
        },
    )
    assert edited.status_code == 404

    bea_year = _year(bea, "Bea")
    bea_export = bea.post("/api/filing/dossier/export")
    assert bea_export.status_code == 201, bea_export.text
    restored = bea.post(
        "/api/filing/dossier/restore",
        json={"filename": bea_export.json()["filename"], "confirmation": "RESTAURER"},
    )
    assert restored.status_code == 200, restored.text

    still = ada.get("/api/ledger/entries", params={"fiscal_year_id": year_id})
    assert still.status_code == 200, still.text
    assert still.json()["entries"][0]["label"] == "Loyer secret"
    content = ada.get(f"/api/filing/documents/{document_id}/content")
    assert content.status_code == 200
    assert content.content == PDF
    assert ada.get(f"/api/ledger/years/{bea_year}/balance").status_code == 404
    ada.close()
    bea.close()


def test_expired_test_token_is_rejected(settings: Settings) -> None:
    token = issue_test_token(TEST_SECRET, expired=True)
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + token}) as client:
        assert client.get("/api/status").status_code == 401


@pytest.mark.parametrize("path", ["/api/filing/backups", "/api/filing/documents/1/content"])
def test_backup_and_document_routes_are_not_public(settings: Settings, path: str) -> None:
    with TestClient(create_app(settings), headers={"Authorization": ""}) as client:
        assert client.get(path).status_code == 401
