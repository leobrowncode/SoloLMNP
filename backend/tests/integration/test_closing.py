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


def _error_codes(response):
    assert response.status_code == 200, response.text
    return [item["code"] for item in response.json()["errors"]]


def _year_status(client, year_id: int = 1) -> str:
    payload = client.get("/api/ledger/setup")
    assert payload.status_code == 200, payload.text
    return next(item["status"] for item in payload.json()["years"] if item["id"] == year_id)


def test_successive_prechecks_require_exact_acknowledgements(client):
    identity = client.post("/api/ledger/activity/identity", json={"siren": "123456789"})
    assert identity.status_code == 200, identity.text
    book(client, "512000", "706000", "100.00")
    book(client, "615000", "401000", "40.00")
    centralize(client, "60.00")

    first = client.get("/api/filing/years/1/precheck")
    assert first.status_code == 200, first.text
    first_codes = [item["code"] for item in first.json()["warnings"]]
    assert first.json()["blocking"] is True
    refused = client.post("/api/filing/years/1/ready", json={"acknowledged": first_codes})
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "CLOSE_BLOCKED"
    assert _year_status(client) == "OPEN"

    fiscal = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    second = client.get("/api/filing/years/1/precheck")
    assert second.status_code == 200, second.text
    assert second.json()["blocking"] is False, second.text
    second_codes = [item["code"] for item in second.json()["warnings"]]
    assert second_codes
    assert set(second_codes) != set(first_codes)
    info_code = second.json()["infos"][0]["code"]

    stale = client.post("/api/filing/years/1/ready", json={"acknowledged": first_codes})
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "WARNINGS_UNACKNOWLEDGED"
    extra = client.post(
        "/api/filing/years/1/ready",
        json={"acknowledged": [*second_codes, "ANCIEN_ACCUSE"]},
    )
    assert extra.status_code == 409
    assert extra.json()["detail"]["code"] == "WARNINGS_UNACKNOWLEDGED"
    with_info = client.post(
        "/api/filing/years/1/ready",
        json={"acknowledged": [*second_codes, info_code]},
    )
    assert with_info.status_code == 409
    assert with_info.json()["detail"]["code"] == "WARNINGS_UNACKNOWLEDGED"
    partial = client.post("/api/filing/years/1/ready", json={"acknowledged": second_codes[:-1]})
    assert partial.status_code == 409
    assert partial.json()["detail"]["code"] == "WARNINGS_UNACKNOWLEDGED"
    assert _year_status(client) == "OPEN"

    ready = client.post("/api/filing/years/1/ready", json={"acknowledged": second_codes})
    assert ready.status_code == 200, ready.text
    assert ready.json()["year_status"] == "READY_TO_CLOSE"
    assert _year_status(client) == "READY_TO_CLOSE"

    bad_close = client.post("/api/filing/years/1/close", json={"confirmation": "FERMER"})
    assert bad_close.status_code == 422
    assert _year_status(client) == "READY_TO_CLOSE"
    assert client.get("/api/filing/years/1/fec").status_code == 409

    closed = client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "CLOSED"
    assert _year_status(client) == "CLOSED"
    fec = client.get("/api/filing/years/1/fec")
    assert fec.status_code == 200, fec.text
    efi = client.get("/api/filing/years/1/efi")
    assert efi.status_code == 200, efi.text
    assert efi.json()["frozen"] is True
    again = client.get("/api/filing/years/1/precheck")
    assert again.status_code == 200, again.text
    assert again.json()["year_status"] == "CLOSED"


def test_fiscal_computation_precedes_precheck_and_close(client):
    identity = client.post("/api/ledger/activity/identity", json={"siren": "123456789"})
    assert identity.status_code == 200, identity.text
    book(client, "512000", "706000", "100.00")
    book(client, "615000", "401000", "40.00")

    before = client.get("/api/filing/years/1/precheck")
    codes = _error_codes(before)
    assert "CENTRALIZATION_REQUIRED" in codes
    assert codes.count("FISCAL_NOT_COMPUTED") == 1
    assert client.post("/api/filing/years/1/ready", json={"acknowledged": []}).status_code == 409
    assert (
        client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"}).status_code
        == 409
    )

    centralize(client, "60.00")
    centralized = _error_codes(client.get("/api/filing/years/1/precheck"))
    assert centralized == ["FISCAL_NOT_COMPUTED"]

    fiscal = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    current = client.get("/api/filing/years/1/precheck")
    assert current.status_code == 200, current.text
    assert current.json()["blocking"] is False, current.text

    book(client, "512000", "108000", "1.00")
    stale = _error_codes(client.get("/api/filing/years/1/precheck"))
    assert "FISCAL_STALE" in stale
    assert "FISCAL_NOT_COMPUTED" not in stale
    assert "CENTRALIZATION_REQUIRED" not in stale
    assert client.post("/api/filing/years/1/ready", json={"acknowledged": []}).status_code == 409

    refreshed = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert refreshed.status_code == 200, refreshed.text
    ready_check = client.get("/api/filing/years/1/precheck")
    assert ready_check.json()["blocking"] is False, ready_check.text
    acknowledged = [item["code"] for item in ready_check.json()["warnings"]]
    ready = client.post("/api/filing/years/1/ready", json={"acknowledged": acknowledged})
    assert ready.status_code == 200, ready.text
    closed = client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "CLOSED"
    fec = client.get("/api/filing/years/1/fec")
    assert fec.status_code == 200, fec.text
    efi = client.get("/api/filing/years/1/efi")
    assert efi.status_code == 200, efi.text
    assert efi.json()["frozen"] is True


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
    assert b"Recherche" in pdf.content
    assert b"pr\xeate \xe0 recopier" not in pdf.content.lower()
    package = client.get("/api/filing/years/1/package").json()
    assert package["declarable"] is False
    assert package["status"] == "research_only"
    assert package["output_status"] == "recherche"
    assert package["copy_complete"] is True
    assert package["exports"]["liasse"]["posture"] == "provisoire"
    assert package["exports"]["fec"]["posture"] == "finale"
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
