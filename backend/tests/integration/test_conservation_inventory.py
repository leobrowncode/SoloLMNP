"""Inventories of supporting documents and backups, including a confirmed restore."""

import base64
import hashlib
import json
import logging
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import pytest

import app.services.backup as backup_service
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


def _document_members(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as bundle:
        return [name for name in bundle.namelist() if name.startswith("documents/")]


def _inject_member(archive: Path, member: str, content: bytes) -> None:
    with zipfile.ZipFile(archive) as bundle:
        payload_bytes = {name: bundle.read(name) for name in bundle.namelist()}
    manifest = json.loads(payload_bytes["manifest.json"])
    files = [item for item in manifest["files"] if item.get("name") != member]
    files.append(
        {
            "name": member,
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    )
    manifest["files"] = files
    encoded = json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()
    payload_bytes["manifest.json"] = encoded
    payload_bytes[member] = content
    temporary = archive.with_suffix(".rewrite.zip")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, data in payload_bytes.items():
            bundle.writestr(name, data)
    temporary.replace(archive)


def _disk_files(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        path.name: path.read_bytes()
        for path in root.iterdir()
        if path.is_file() and not path.is_symlink()
    }


def test_gitkeep_is_absent_from_new_archives_and_ignored_on_restore(client, settings):
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    (settings.documents_dir / ".gitkeep").write_bytes(b"")
    (settings.documents_dir / "orphelin.pdf").write_bytes(b"%PDF-1.4 orphelin")
    _book(client, "PIECE-1")
    uploaded = client.post("/api/filing/documents", json=_pdf("une.pdf"))
    assert uploaded.status_code == 201, uploaded.text
    created = client.post("/api/filing/backup")
    assert created.status_code == 201, created.text
    filename = created.json()["filename"]
    archive = settings.database_path.parent / "backups" / filename
    members = _document_members(archive)
    assert members
    assert all(not Path(name).name.startswith(".") for name in members)
    assert "documents/.gitkeep" not in members
    assert "documents/orphelin.pdf" not in members
    assert len(members) == 1

    _inject_member(archive, "documents/.gitkeep", b"")
    checked = client.post("/api/filing/backups/verify", json={"filename": filename})
    assert checked.status_code == 200, checked.text
    assert checked.json()["integrity"]["status"] == "ok"
    assert checked.json()["integrity"]["message"] == "Contrôle d’intégrité réussi."

    _book(client, "PIECE-2")
    second = client.post("/api/filing/documents", json=_pdf("deux.pdf"))
    assert second.status_code == 201, second.text
    assert _entry_count(client) == 2

    restored = client.post(
        "/api/filing/backup/restore",
        json={"filename": filename, "confirmation": "RESTAURER"},
    )
    assert restored.status_code == 200, restored.text
    assert _entry_count(client) == 1
    names = sorted(path.name for path in settings.documents_dir.iterdir() if path.is_file())
    assert names == [Path(members[0]).name]
    assert ".gitkeep" not in names
    assert "orphelin.pdf" not in names
    listed = client.get("/api/filing/documents")
    assert [item["original_name"] for item in listed.json()["documents"]] == ["une.pdf"]

    safety = restored.json()["pre_restore_backup"]
    safety_path = settings.database_path.parent / "backups" / safety
    safety_members = _document_members(safety_path)
    assert safety_members
    assert all(not Path(name).name.startswith(".") for name in safety_members)
    assert "documents/.gitkeep" not in safety_members
    safety_check = client.post("/api/filing/backups/verify", json={"filename": safety})
    assert safety_check.status_code == 200, safety_check.text
    assert safety_check.json()["integrity"]["status"] == "ok"
    safety_restore = client.post(
        "/api/filing/backup/restore",
        json={"filename": safety, "confirmation": "RESTAURER"},
    )
    assert safety_restore.status_code == 200, safety_restore.text
    assert _entry_count(client) == 2
    documents = client.get("/api/filing/documents").json()["documents"]
    originals = sorted(item["original_name"] for item in documents)
    assert originals == ["deux.pdf", "une.pdf"]


def test_verify_and_restore_refuse_the_same_malicious_document_path(client, settings):
    _book(client, "PIECE-1")
    uploaded = client.post("/api/filing/documents", json=_pdf("une.pdf"))
    assert uploaded.status_code == 201, uploaded.text
    created = client.post("/api/filing/backup")
    assert created.status_code == 201, created.text
    filename = created.json()["filename"]
    archive = settings.database_path.parent / "backups" / filename
    _inject_member(archive, "documents/sous-dossier/secret.pdf", b"%PDF-1.4 secret")
    before_entries = _entry_count(client)
    before_files = _disk_files(settings.documents_dir)

    preview = client.get("/api/filing/backups/preview", params={"filename": filename})
    checked = client.post("/api/filing/backups/verify", json={"filename": filename})
    restored = client.post(
        "/api/filing/backup/restore",
        json={"filename": filename, "confirmation": "RESTAURER"},
    )
    message = "Chemin de document refusé."
    for response in (preview, checked, restored):
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "BACKUP_REJECTED"
        assert response.json()["detail"]["message"] == message
    recorded = next(
        item
        for item in client.get("/api/filing/backups").json()["backups"]
        if item["filename"] == filename
    )
    assert recorded["integrity"]["status"] == "failed"
    assert recorded["integrity"]["message"] == message
    assert _entry_count(client) == before_entries
    assert _disk_files(settings.documents_dir) == before_files
    assert not (settings.documents_dir / "secret.pdf").exists()
    assert not (settings.documents_dir / "sous-dossier").exists()


def test_restore_failure_rolls_back_database_and_documents(client, settings, monkeypatch):
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    (settings.documents_dir / ".gitkeep").write_bytes(b"keep")
    _book(client, "PIECE-1")
    uploaded = client.post("/api/filing/documents", json=_pdf("une.pdf"))
    assert uploaded.status_code == 201, uploaded.text
    created = client.post("/api/filing/backup")
    assert created.status_code == 201, created.text
    _book(client, "PIECE-2")
    before_entries = _entry_count(client)
    before_files = _disk_files(settings.documents_dir)
    assert ".gitkeep" in before_files
    real = backup_service._replace_documents

    def fail_after(root: Path, files: list[tuple[str, bytes]]) -> None:
        real(root, files)
        raise RuntimeError("remplacement interrompu")

    monkeypatch.setattr(backup_service, "_replace_documents", fail_after)
    with pytest.raises(RuntimeError, match="remplacement interrompu"):
        client.post(
            "/api/filing/backup/restore",
            json={"filename": created.json()["filename"], "confirmation": "RESTAURER"},
        )
    assert _entry_count(client) == before_entries
    assert _disk_files(settings.documents_dir) == before_files


def test_restore_rollback_failure_is_logged(client, settings, monkeypatch, caplog):
    _book(client, "PIECE-1")
    created = client.post("/api/filing/backup")
    assert created.status_code == 201, created.text

    def fail_documents(root: Path, files: list[tuple[str, bytes]]) -> None:
        raise RuntimeError("remplacement interrompu")

    def fail_rollback(*_args: object, **_kwargs: object) -> None:
        raise OSError("retour arrière impossible")

    monkeypatch.setattr(backup_service, "_replace_documents", fail_documents)
    monkeypatch.setattr(backup_service, "_restore_database_file", fail_rollback)
    with caplog.at_level(logging.ERROR, logger="app.services.backup"):
        with pytest.raises(OSError, match="retour arrière impossible"):
            client.post(
                "/api/filing/backup/restore",
                json={"filename": created.json()["filename"], "confirmation": "RESTAURER"},
            )
    assert "Échec du retour arrière de la restauration." in caplog.text
