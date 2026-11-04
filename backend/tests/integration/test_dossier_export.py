"""Portable dossier export on the engine selected by TEST_DATABASE_URL."""

import base64
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.main import create_app

PDF = b"%PDF-1.4 justificatif"


@pytest.fixture
def client(settings, database):
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as api:
        assert (
            api.post(
                "/api/ledger/activity",
                json={"activity_name": "Test fictif", "activity_start_date": "2025-01-01"},
            ).status_code
            == 201
        )
        assert (
            api.post(
                "/api/ledger/years",
                json={
                    "year": 2025,
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                    "fiscal_vintage": "2025",
                },
            ).status_code
            == 201
        )
        yield api


def _payload(piece: str = "TEST-001", day: str = "2025-02-01") -> dict[str, object]:
    return {
        "fiscal_year_id": 1,
        "journal_code": "BQ",
        "accounting_date": day,
        "piece_reference": piece,
        "piece_date": day,
        "label": "Loyer fictif",
        "lines": [
            {"account_number": "512000", "label": "Banque", "debit": "123.45", "credit": "0.00"},
            {"account_number": "706000", "label": "Produit", "debit": "0.00", "credit": "123.45"},
        ],
    }


def _validate(
    api: TestClient, piece: str = "TEST-001", day: str = "2025-02-01"
) -> dict[str, object]:
    drafted = api.post("/api/ledger/entries", json=_payload(piece, day))
    assert drafted.status_code == 201, drafted.text
    entry = drafted.json()
    posted = api.post(
        f"/api/ledger/entries/{entry['id']}/validate",
        json={"expected_version": entry["version"]},
    )
    assert posted.status_code == 200, posted.text
    return posted.json()


def _upload(api: TestClient, name: str = "quittance.pdf") -> dict[str, object]:
    response = api.post(
        "/api/filing/documents",
        json={
            "filename": name,
            "media_type": "application/pdf",
            "content_base64": base64.b64encode(PDF).decode(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _export(api: TestClient) -> str:
    created = api.post("/api/filing/dossier/export")
    assert created.status_code == 201, created.text
    filename = created.json()["filename"]
    assert filename.startswith("dossier-") and filename.endswith(".zip")
    return filename


def test_documents_stay_private_and_dossier_roundtrip_restores_reversal(
    client: TestClient, settings, database
) -> None:
    original = _validate(client)
    reversal = client.post(
        f"/api/ledger/entries/{original['id']}/reverse",
        json={
            "accounting_date": "2025-02-02",
            "piece_reference": "EXT-001",
            "reason": "Correction fictive",
        },
    )
    assert reversal.status_code == 201, reversal.text
    uploaded = _upload(client)
    assert "http" not in client.get("/api/filing/documents").text
    assert "vercel" not in client.get("/api/filing/documents").text
    content = client.get(f"/api/filing/documents/{uploaded['id']}/content")
    assert content.status_code == 200
    assert content.content == PDF
    assert content.headers["cache-control"] == "private, no-store"
    assert content.headers["x-content-type-options"] == "nosniff"
    assert content.headers["x-content-sha256"] == uploaded["sha256"]

    filename = _export(client)
    listed = client.get("/api/filing/dossier/exports")
    assert listed.status_code == 200
    assert listed.json()["backups"][0]["filename"] == filename
    assert listed.json()["backups"][0]["integrity"]["status"] == "unchecked"
    verified = client.post("/api/filing/dossier/exports/verify", json={"filename": filename})
    assert verified.status_code == 200, verified.text
    assert verified.json()["integrity"]["status"] == "ok"

    _validate(client, "TEST-002", "2025-03-01")
    _upload(client, "autre.pdf")
    (settings.documents_dir / ".gitkeep").write_text("", encoding="utf-8")
    (settings.documents_dir / "stray.pdf").write_bytes(b"%PDF-stray")
    preview = client.get("/api/filing/dossier/exports/preview", params={"filename": filename})
    assert preview.status_code == 200, preview.text
    assert preview.json()["current"]["entries"] == 3
    assert preview.json()["backup"]["entries"] == 2

    restored = client.post(
        "/api/filing/dossier/restore",
        json={"filename": filename, "confirmation": "RESTAURER"},
    )
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert body["restored_from"] == filename
    assert body["entries"] == 2
    assert body["pre_restore_backup"].startswith("dossier-")
    ledger = client.get("/api/ledger/years/1/general-ledger?account_number=512000").json()
    assert [line["balance"] for line in ledger["lines"]] == ["123.45", "0.00"]
    with database.engine.connect() as connection:
        links = connection.execute(
            text("SELECT id, reversal_of_id FROM accounting_entry ORDER BY id")
        ).all()
    assert len(links) == 2
    assert links[1][1] == links[0][0]
    documents = client.get("/api/filing/documents").json()["documents"]
    assert len(documents) == 1
    assert client.get(f"/api/filing/documents/{documents[0]['id']}/content").content == PDF
    names = sorted(path.name for path in Path(settings.documents_dir).iterdir())
    assert ".gitkeep" in names
    assert "stray.pdf" not in names
    assert sum(name.endswith(".pdf") for name in names) == 1
    with pytest.raises(IntegrityError), database.engine.begin() as connection:
        connection.execute(
            text("UPDATE accounting_entry SET label='changed' WHERE status='VALIDATED'")
        )
    again = client.post("/api/ledger/entries", json=_payload("TEST-003", "2025-04-01"))
    assert again.status_code == 201, again.text

    removed = client.delete(f"/api/filing/documents/{documents[0]['id']}")
    assert removed.status_code == 200
    assert removed.json() == {"id": documents[0]["id"], "deleted": True}
    assert client.get("/api/filing/documents").json()["documents"] == []
    assert client.get(f"/api/ledger/entries/{original['id']}").status_code == 200
    remaining = [path.name for path in Path(settings.documents_dir).iterdir()]
    assert remaining == [".gitkeep"]


def test_tampered_archive_is_refused_and_leaves_the_dossier(client: TestClient, settings) -> None:
    _validate(client)
    filename = _export(client)
    path = settings.documents_dir.parent / "dossier-exports" / filename
    raw = bytearray(path.read_bytes())
    raw[-30] ^= 0xFF
    path.write_bytes(raw)
    before = client.get("/api/ledger/years/1/balance").json()["total_debit"]
    refused = client.post("/api/filing/dossier/exports/verify", json={"filename": filename})
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "DOSSIER_REJECTED"
    restore = client.post(
        "/api/filing/dossier/restore",
        json={"filename": filename, "confirmation": "RESTAURER"},
    )
    assert restore.status_code == 422
    assert restore.json()["detail"]["code"] == "DOSSIER_REJECTED"
    assert client.get("/api/ledger/years/1/balance").json()["total_debit"] == before
    unknown = client.post("/api/filing/dossier/exports/verify", json={"filename": "nope.zip"})
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["code"] == "DOSSIER_NOT_FOUND"


def test_failed_document_sync_rolls_the_rows_back(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _validate(client)
    _upload(client)
    filename = _export(client)
    _validate(client, "TEST-002", "2025-03-01")

    def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("sync")

    monkeypatch.setattr("app.services.dossier_export.sync_documents", explode)
    with pytest.raises(RuntimeError, match="sync"):
        client.post(
            "/api/filing/dossier/restore",
            json={"filename": filename, "confirmation": "RESTAURER"},
        )
    balance = client.get("/api/ledger/years/1/balance").json()
    assert balance["total_debit"] == "246.90"
    assert len(client.get("/api/filing/documents").json()["documents"]) == 1


def test_failed_row_rollback_is_logged(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _validate(client)
    filename = _export(client)
    real = __import__("app.services.dossier_export", fromlist=["replace_rows"]).replace_rows
    calls = {"n": 0}

    def wrapped(database: object, payload: object, owner_id: int) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("rollback")
        real(database, payload, owner_id)

    def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("sync")

    monkeypatch.setattr("app.services.dossier_export.replace_rows", wrapped)
    monkeypatch.setattr("app.services.dossier_export.sync_documents", explode)
    with (
        caplog.at_level(logging.ERROR, logger="app.services.dossier_export"),
        pytest.raises(RuntimeError, match="rollback"),
    ):
        client.post(
            "/api/filing/dossier/restore",
            json={"filename": filename, "confirmation": "RESTAURER"},
        )
    assert calls["n"] == 2
    assert "Échec du retour arrière de la restauration." in caplog.text
