"""Inventories of supporting documents and backups, including a confirmed restore."""

import base64
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import pytest

from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_ledger import draft, payload, post


@pytest.fixture
def client(seeded_client):  # noqa: F811
    return seeded_client


def _pdf(name: str = "quittance.pdf") -> dict[str, str]:
    return {
        "filename": name,
        "media_type": "application/pdf",
        "content_base64": base64.b64encode(b"%PDF-1.4 justificatif").decode(),
    }


def _book(client, piece: str):
    data = payload()
    data["piece_reference"] = piece
    response = post(client, draft(client, data))
    assert response.status_code == 200, response.text
    return response.json()


def _entry_count(client) -> int:
    response = client.get("/api/ledger/entries", params={"fiscal_year_id": 1, "limit": 200})
    assert response.status_code == 200, response.text
    return int(response.json()["count"])


def _archive_entries(path: Path) -> int:
    with zipfile.ZipFile(path) as bundle, tempfile.TemporaryDirectory() as folder:
        bundle.extract("database.sqlite3", folder)
        connection = sqlite3.connect(Path(folder) / "database.sqlite3")
        try:
            row = connection.execute("SELECT COUNT(*) FROM accounting_entry").fetchone()
        finally:
            connection.close()
    assert row is not None
    return int(row[0])


def test_document_list_links_by_number_date_and_piece_without_touching_the_entry(client):
    first = draft(client)
    second = draft(client)
    assert first["entry_number"] is None
    uploaded = client.post("/api/filing/documents", json=_pdf())
    assert uploaded.status_code == 201, uploaded.text
    empty_search = client.get("/api/filing/entries")
    assert empty_search.status_code == 422
    assert empty_search.json()["detail"]["code"] == "ENTRY_SEARCH"
    assert empty_search.json()["detail"]["help"] == "ecriture"
    ambiguous = client.get(
        "/api/filing/entries",
        params={"piece": "TEST-001", "entry_date": "2025-02-01"},
    )
    assert ambiguous.status_code == 200, ambiguous.text
    assert len(ambiguous.json()["entries"]) == 2
    assert "id" not in ambiguous.json()["entries"][0]
    refused = client.post(
        f"/api/filing/documents/{uploaded.json()['id']}/link",
        json={
            "entry_number": None,
            "accounting_date": "2025-02-01",
            "piece_reference": "TEST-001",
        },
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "ENTRY_AMBIGUOUS"

    posted = post(client, first)
    assert posted.status_code == 200, posted.text
    before = client.get(f"/api/ledger/entries/{posted.json()['id']}").json()
    found = client.get(
        "/api/filing/entries",
        params={
            "number": before["entry_number"],
            "entry_date": before["accounting_date"],
            "piece": before["piece_reference"],
        },
    )
    assert found.status_code == 200, found.text
    assert found.json()["entries"] == [
        {
            "entry_number": before["entry_number"],
            "accounting_date": before["accounting_date"],
            "piece_reference": before["piece_reference"],
            "piece_date": before["piece_date"],
            "label": before["label"],
            "status": "VALIDATED",
            "year": 2025,
        }
    ]
    linked = client.post(
        f"/api/filing/documents/{uploaded.json()['id']}/link",
        json={
            "entry_number": before["entry_number"],
            "accounting_date": before["accounting_date"],
            "piece_reference": before["piece_reference"],
        },
    )
    assert linked.status_code == 200, linked.text
    assert "entry_id" not in linked.json()
    assert linked.json()["entry"]["entry_number"] == before["entry_number"]
    after = client.get(f"/api/ledger/entries/{posted.json()['id']}").json()
    assert after == before
    listed = client.get("/api/filing/documents")
    assert listed.status_code == 200, listed.text
    row = listed.json()["documents"][0]
    assert row["original_name"] == "quittance.pdf"
    assert row["created_at"]
    assert row["media_label"] == "PDF"
    assert row["media_type"] == "application/pdf"
    assert row["size"] == len(b"%PDF-1.4 justificatif")
    assert len(row["sha256"]) == 64
    assert row["entry"]["piece_reference"] == "TEST-001"
    assert row["entry"]["accounting_date"] == "2025-02-01"
    untouched = client.get(f"/api/ledger/entries/{second['id']}").json()
    assert untouched["status"] == "DRAFT"
    assert untouched["entry_number"] is None


def test_backup_list_verify_preview_and_confirmed_restore(client, settings):
    original = _book(client, "PIECE-1")
    before = client.get(f"/api/ledger/entries/{original['id']}").json()
    first_document = client.post("/api/filing/documents", json=_pdf("une.pdf"))
    assert first_document.status_code == 201, first_document.text
    created = client.post("/api/filing/backup")
    assert created.status_code == 201, created.text
    filename = created.json()["filename"]
    archive = settings.database_path.parent / "backups" / filename

    listed = client.get("/api/filing/backups")
    assert listed.status_code == 200, listed.text
    row = listed.json()["backups"][0]
    assert row["filename"] == filename
    assert row["created_at"]
    assert row["size"] == archive.stat().st_size
    assert row["application_version"]
    assert row["schema_revision"]
    assert row["sha256"] == created.json()["sha256"]
    assert row["integrity"]["status"] == "unchecked"

    checked = client.post("/api/filing/backups/verify", json={"filename": filename})
    assert checked.status_code == 200, checked.text
    assert checked.json()["integrity"]["status"] == "ok"
    assert checked.json()["integrity"]["checked_at"]
    again = client.get("/api/filing/backups").json()["backups"][0]
    assert again["integrity"]["status"] == "ok"
    assert again["integrity"]["message"]

    extra = _book(client, "PIECE-2")
    second_document = client.post("/api/filing/documents", json=_pdf("deux.pdf"))
    assert second_document.status_code == 201, second_document.text
    assert _entry_count(client) == 2
    assert len(list(settings.documents_dir.iterdir())) == 2

    preview = client.get("/api/filing/backups/preview", params={"filename": filename})
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["backup_date"]
    assert body["current"] == {"entries": 2, "years": 1}
    assert body["backup"] == {"entries": 1, "years": 1}

    missing = client.post(
        "/api/filing/backup/restore",
        json={"filename": filename, "confirmation": "OUVRIR"},
    )
    assert missing.status_code == 422
    assert _entry_count(client) == 2
    unknown = client.post(
        "/api/filing/backup/restore",
        json={"filename": "sololmnp-absent.zip", "confirmation": "RESTAURER"},
    )
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["code"] == "BACKUP_NOT_FOUND"

    restored = client.post(
        "/api/filing/backup/restore",
        json={"filename": filename, "confirmation": "RESTAURER"},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["restored_from"] == filename
    assert restored.json()["entries"] == 1
    assert restored.json()["years"] == 1
    safety = restored.json()["pre_restore_backup"]
    assert safety != filename
    safety_path = settings.database_path.parent / "backups" / safety
    assert safety_path.is_file()
    assert _archive_entries(safety_path) == 2
    assert _entry_count(client) == 1
    assert client.get(f"/api/ledger/entries/{extra['id']}").status_code == 404
    assert client.get(f"/api/ledger/entries/{original['id']}").json() == before
    names = sorted(path.name for path in settings.documents_dir.iterdir() if path.is_file())
    assert len(names) == 1
    documents = client.get("/api/filing/documents")
    assert documents.status_code == 200, documents.text
    assert [item["original_name"] for item in documents.json()["documents"]] == ["une.pdf"]

    raw = bytearray(archive.read_bytes())
    raw[-20] ^= 0x01
    archive.write_bytes(raw)
    rejected = client.post("/api/filing/backups/verify", json={"filename": filename})
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "BACKUP_REJECTED"
    failed = next(
        item
        for item in client.get("/api/filing/backups").json()["backups"]
        if item["filename"] == filename
    )
    assert failed["integrity"]["status"] == "failed"
