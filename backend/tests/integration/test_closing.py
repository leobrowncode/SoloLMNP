import base64
import io
import json
import zipfile
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


def test_fiscal_computation_precedes_close(client):
    identity = client.post("/api/ledger/activity/identity", json={"siren": "123456789"})
    assert identity.status_code == 200, identity.text
    book(client, "512000", "706000", "100.00")
    book(client, "615000", "401000", "40.00")
    centralize(client, "60.00")

    missing = client.get("/api/filing/years/1/precheck")
    assert missing.status_code == 200, missing.text
    missing_body = missing.json()
    assert missing_body["blocking"] is True
    assert [item["code"] for item in missing_body["errors"]].count("FISCAL_NOT_COMPUTED") == 1
    assert client.post("/api/filing/years/1/ready", json={"acknowledged": []}).status_code == 409
    assert (
        client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"}).status_code
        == 409
    )

    fiscal = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    fresh = client.get("/api/filing/years/1/precheck").json()
    fresh_codes = [item["code"] for item in fresh["errors"]]
    assert "FISCAL_NOT_COMPUTED" not in fresh_codes
    assert "FISCAL_STALE" not in fresh_codes

    book(client, "512000", "108000", "10.00")
    stale = client.get("/api/filing/years/1/precheck").json()
    assert stale["blocking"] is True
    assert any(item["code"] == "FISCAL_STALE" for item in stale["errors"])
    assert all(item["code"] != "FISCAL_NOT_COMPUTED" for item in stale["errors"])

    recomputed = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert recomputed.status_code == 200, recomputed.text
    ready_check = client.get("/api/filing/years/1/precheck").json()
    assert ready_check["blocking"] is False, ready_check
    codes = [item["code"] for item in ready_check["warnings"]]
    prepared = client.post("/api/filing/years/1/ready", json={"acknowledged": codes})
    assert prepared.status_code == 200, prepared.text
    closed = client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "CLOSED"


def test_close_reopen_fec_efi_and_documents(client, settings):
    identity = client.post("/api/ledger/activity/identity", json={"siren": "123456789"})
    assert identity.status_code == 200, identity.text
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
    assert 'filename="123456789FEC' in first.headers["content-disposition"]
    archive = client.get("/api/filing/years/1/archive")
    assert archive.status_code == 200, archive.text
    assert archive.content == client.get("/api/filing/years/1/archive").content
    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        names = set(bundle.namelist())
        fec_name = next(
            name
            for name in sorted(names)
            if name.startswith("123456789FEC") and not name.endswith("_description.txt")
        )
        assert bundle.read(fec_name) == first.content
        assert "SHA256SUMS.txt" in names
        assert any(name.endswith("_description.txt") for name in names)
        assert any(name.endswith(".pdf") for name in names)
        description = bundle.read(fec_name.replace(".txt", "_description.txt")).decode()
        assert "A47 A-1" in description
    efi = client.get("/api/filing/years/1/efi").json()
    assert efi["transmission"] is False
    assert efi["frozen"] is True
    assert efi["personal_return"]["separated_from_liasse"] is True
    assert [line["case"] for line in efi["personal_return"]["lines"]] == ["5NA", "5NY"]
    assert efi["liasse"]["fields"][0]["expression"]
    pdf = client.get("/api/filing/years/1/efi.pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF-")
    assert b"ready" in pdf.content
    package = client.get("/api/filing/years/1/package").json()
    assert package["declarable"] is True
    assert package["status"] == "ready"
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
    rejected = client.post(
        "/api/filing/documents",
        json={
            "filename": "photo.jpg",
            "media_type": "image/jpeg",
            "content_base64": base64.b64encode(b"%PDF-1.4 test").decode(),
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "DOCUMENT_SIGNATURE"


def test_backup_round_trip_rejects_escape(client, settings):
    book(client, "512000", "706000", "10.00")
    created = client.post("/api/filing/backup")
    assert created.status_code == 201, created.text
    archive = settings.database_path.parent / "backups" / created.json()["filename"]
    with zipfile.ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
    assert {item["vintage"] for item in manifest["fiscal_vintages"]} >= {"2025", "2026"}
    restored = client.post(
        "/api/filing/backup/restore", json={"filename": created.json()["filename"]}
    )
    assert restored.status_code == 200, restored.text
    escaped = client.post("/api/filing/backup/restore", json={"filename": "../sololmnp.sqlite3"})
    assert escaped.status_code == 422
