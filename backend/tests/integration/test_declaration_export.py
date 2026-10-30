"""EFI copy sheet and 2042-C-PRO: explained amounts, blocked boxes, archival exports."""

from __future__ import annotations

import hashlib
import json

import pytest

from app.domain.filing.declaration import WORK_MARKER
from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_statements import book


@pytest.fixture
def client(seeded_client):  # noqa: F811
    return seeded_client


def test_vintage_2025_explains_amounts_and_archives_them(client):
    # 1 000,00 € de loyers − 80,00 € d’intérêts = 920,00 €. Pas de dotation.
    # CGI art. 39 C II : sans dotation, le résultat fiscal reste le résultat comptable.
    rent = book(client, "512000", "706000", "1000.00")
    interest = book(client, "661000", "512000", "80.00")
    assert client.post("/api/fiscal/years/1", json={"adjustments": []}).status_code == 200
    assert (
        client.post("/api/ledger/activity/identity", json={"siren": "123456789"}).status_code == 200
    )
    sheet = client.get("/api/filing/years/1/efi").json()
    assert sheet["status"] == "research_only"
    assert sheet["declarable"] is False
    assert sheet["work_marker"] == WORK_MARKER
    assert sheet["manual_only"] is True
    assert sheet["transmission"] is False
    declaration = sheet["declaration"]
    assert declaration["status"] == "research_only"
    assert declaration["declarable"] is False
    assert declaration["edi"] is False
    assert declaration["scraping"] is False
    assert declaration["vintage"] == "2025"
    assert declaration["rules_version"] == "research-2"
    assert len(declaration["rules_sha256"]) == 64
    assert declaration["rules_match_computation"] is True
    amounts = {item["code"]: item for item in declaration["explanations"]}
    assert amounts["accounting_result"]["amount"] == "920.00"
    assert amounts["additions"]["amount"] == "0.00"
    assert amounts["deductible_depreciation"]["amount"] == "0.00"
    assert amounts["fiscal_before_losses"]["amount"] == "920.00"
    assert amounts["fiscal_result"]["amount"] == "920.00"
    rule = amounts["deductible_depreciation"]["rules"][0]
    assert rule["id"] == "RULE-LMNP-DEPRECIATION-LIMIT-001"
    assert rule["source_url"].startswith("https://www.legifrance.gouv.fr/")
    entry_ids = {item["id"] for item in amounts["accounting_result"]["entries"]}
    assert rent["id"] in entry_ids
    assert interest["id"] in entry_ids
    services = next(row for row in declaration["efi_rows"] if row["case"] == "217")
    assert services["form"] == "2033-B-SD"
    assert services["case_status"] == "verified"
    assert services["amount"] == "1000.00"
    assert services["source_url"].startswith("https://www.impots.gouv.fr/")
    assert rent["id"] in services["entry_ids"]
    unnumbered = next(
        row for row in declaration["efi_rows"] if row["code"] == "2031_RESULTAT_BENEFICE"
    )
    assert unnumbered["case"] is None
    assert unnumbered["case_status"] == "unnumbered"
    personal = sheet["personal_return"]
    assert personal["status"] == "verified"
    assert personal["cerfa"] == "11222*28"
    assert personal["declarable"] is False
    by_case = {line["case"]: line for line in personal["lines"]}
    assert by_case["5NA"]["amount"] == "920.00"
    assert by_case["5NA"]["served"] is True
    assert by_case["5NY"]["amount"] == "0.00"
    assert by_case["5NY"]["served"] is False
    blocked = {item["case"] for item in personal["blocked_cases"]}
    assert blocked == {"5NK", "5NZ"}
    assert "5NK" not in by_case
    assert "5NZ" not in by_case

    archived = client.get("/api/filing/years/1/efi.json")
    assert archived.status_code == 200
    assert archived.headers["x-export-posture"] == "provisoire"
    assert archived.headers["x-content-sha256"] == hashlib.sha256(archived.content).hexdigest()
    body = json.loads(archived.content)
    assert body["marker"] == WORK_MARKER
    assert body["status"] == "research_only"
    assert body["declarable"] is False
    assert body["vintage"] == "2025"
    assert body["rules_version"] == "research-2"
    assert body["rules_sha256"] == declaration["rules_sha256"]
    benefit = next(
        row for row in body["rows"] if row["form"] == "2042-C-PRO" and row["case"] == "5NA"
    )
    assert benefit["amount"] == "920.00"
    assert not any(row["case"] == "5NK" for row in body["rows"])

    table = client.get("/api/filing/years/1/efi.csv")
    assert table.status_code == 200
    assert table.headers["x-content-sha256"] == hashlib.sha256(table.content).hexdigest()
    text = table.content.decode()
    assert WORK_MARKER in text
    assert "vintage=2025" in text
    assert f"rules_sha256={declaration['rules_sha256']}" in text
    assert "2033-B-SD;217;verified;" in text
    assert "2042-C-PRO;5NA;verified;" in text
    assert "5NK" not in text.split("blocked_cases")[0]

    pdf = client.get("/api/filing/years/1/efi.pdf")
    assert WORK_MARKER.encode("cp1252") in pdf.content
    assert "Case 5NA".encode("cp1252") in pdf.content
    assert "Ne pas utiliser la case 5NK".encode("cp1252") in pdf.content
    assert "Saisie et envoi manuels".encode("cp1252") in pdf.content


def test_blocked_export_matches_the_pdf_gate(client):
    book(client, "512000", "706000", "1000.00")
    assert client.post("/api/fiscal/years/1", json={"adjustments": []}).status_code == 200
    refused = client.get("/api/filing/years/1/efi.json")
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] in {"SIREN_MANQUANT", "EXPORT_BLOCKED"}
    assert client.get("/api/filing/years/1/efi.csv").status_code == 409
    assert client.get("/api/filing/years/1/efi.pdf").status_code == 409
