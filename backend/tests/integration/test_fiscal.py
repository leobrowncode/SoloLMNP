import io
import json
import zipfile
from typing import Any

import pytest

from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_statements import book, report


@pytest.fixture
def client(seeded_client):  # noqa: F811
    return seeded_client


def test_depreciation_limit_is_separate_from_the_ledger(client):
    book(client, "411000", "706000", "1000.00")
    book(client, "615000", "401000", "400.00")
    book(client, "681100", "281840", "800.00")
    before = report(client)
    first = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "research_only"
    assert body["declarable"] is False
    assert body["output_status"] == "recherche"
    assert body["output_label"] == "Recherche"
    assert body["accounting_result"] == before["income_statement"]["result"] == "-200.00"
    assert body["deductible_depreciation"] == "600.00"
    assert body["unused_depreciation"] == "200.00"
    assert body["fiscal_result"] == "0.00"
    assert body["tax_loss"] == "0.00"
    assert body["imputed_on_global_income"] == "0.00"
    assert body["details"]["prior_carry_forward_use"]["status"] == "enabled"
    assert body["details"]["prior_depreciation_used"] == "0.00"
    assert body["details"]["operating_income"] == "1000.00"
    assert body["details"]["other_charges"] == "400.00"
    assert body["details"]["prior_depreciation_available"] == "0.00"
    assert body["details"]["depreciation_reports"] == []
    assert body["details"]["depreciation_categories"] == []
    assert "0 €" in body["details"]["goal_hint"]
    assert report(client)["income_statement"]["total_expenses"] == "1200.00"
    replay = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert replay.json()["replayed"] is True
    assert replay.json()["id"] == body["id"]


def test_tax_loss_is_not_a_depreciation_carry_forward(client):
    book(client, "615000", "401000", "250.00")
    book(client, "512000", "706000", "100.00")
    body = client.post("/api/fiscal/years/1", json={"adjustments": []}).json()
    assert body["fiscal_result"] == "-150.00"
    assert body["tax_loss"] == "150.00"
    assert body["unused_depreciation"] == "0.00"
    assert "RULE-LMNP-LOSS-001" in body["details"]["applied_rules"]
    assert body["details"]["scope_rules"] == ["RULE-LMNP-BIC-001"]
    assert "RULE-LMNP-BIC-001" not in body["details"]["blocked_rules"]
    assert "RULE-LMNP-BIC-001" not in body["details"]["applied_rules"]


def test_partial_charge_stays_in_the_ledger(client):
    book(client, "512000", "706000", "100.00")
    book(client, "622000", "401000", "80.00")
    body = client.post(
        "/api/fiscal/years/1",
        json={
            "adjustments": [
                {
                    "account_number": "622000",
                    "amount": "30.00",
                    "justification": "Quote-part non déductible confirmée, hors ledger.",
                }
            ]
        },
    ).json()
    assert body["non_deductible"] == "30.00"
    assert body["fiscal_result"] == "50.00"
    assert report(client)["income_statement"]["total_expenses"] == "80.00"
    too_much = client.post(
        "/api/fiscal/years/1",
        json={
            "adjustments": [
                {
                    "account_number": "622000",
                    "amount": "80.01",
                    "justification": "Montant supérieur à la charge comptabilisée.",
                }
            ]
        },
    )
    assert too_much.status_code == 422
    assert too_much.json()["detail"]["code"] == "ADJUSTMENT_TOO_LARGE"
    kept = client.get("/api/fiscal/years/1")
    assert kept.status_code == 200, kept.text
    assert kept.json()["id"] == body["id"]
    assert kept.json()["fiscal_result"] == body["fiscal_result"]


def test_latest_computation_exposes_its_date_and_a_moved_ledger(client):
    book(client, "512000", "706000", "1000.00")
    created = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert created.status_code == 200, created.text
    body = created.json()
    loaded = client.get("/api/fiscal/years/1")
    assert loaded.status_code == 200, loaded.text
    current = loaded.json()
    assert current["id"] == body["id"]
    assert current["computed_at"].endswith("Z")
    assert current["status"] == "research_only"
    assert current["declarable"] is False
    assert current["ledger_sha256"] == current["current_ledger_sha256"] == body["ledger_sha256"]
    assert len(current["ledger_sha256"]) == 64
    assert current["invalidated"] is False
    assert current["structuring_sha256"] == current["current_structuring_sha256"]
    assert len(current["structuring_sha256"]) == 64
    book(client, "615000", "401000", "15.00")
    stale = client.get("/api/fiscal/years/1")
    assert stale.status_code == 200, stale.text
    moved = stale.json()
    assert moved["id"] == body["id"]
    assert moved["fiscal_result"] == body["fiscal_result"]
    assert moved["ledger_sha256"] == body["ledger_sha256"]
    assert moved["current_ledger_sha256"] != moved["ledger_sha256"]
    assert moved["invalidated"] is False
    assert moved["structuring_sha256"] == current["structuring_sha256"]
    assert moved["current_structuring_sha256"] == current["structuring_sha256"]
    missing = client.get("/api/fiscal/years/999")
    assert missing.status_code == 404


def test_vintages_stay_research_only(client):
    payload = client.get("/api/fiscal/vintages").json()
    assert payload["declarable"] is False
    assert payload["status"] == "research_only"
    assert {row["vintage"] for row in payload["vintages"]} == {"2025", "2026"}
    assert all(row["scope"] == ["RULE-LMNP-BIC-001"] for row in payload["vintages"])
    assert all(row["blocked"] == [] for row in payload["vintages"])
    assert client.get("/api/status").json()["fiscal"]["status"] == "research_only"


def identify(client):
    response = client.post("/api/ledger/activity/identity", json={"siren": "123456789"})
    assert response.status_code == 200, response.text


def test_liasse_keeps_interest_out_of_operating_charges(client):
    book(client, "512000", "706000", "1000.00")
    book(client, "661000", "512000", "80.00")
    fiscal = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    missing = client.get("/api/filing/years/1/efi").json()
    assert missing["declarable"] is False
    assert [item["code"] for item in missing["blocking"]] == ["SIREN_MANQUANT"]
    identify(client)
    sheet = client.get("/api/filing/years/1/efi").json()
    assert sheet["transmission"] is False
    assert sheet["frozen"] is False
    assert sheet["blocking"] == []
    by_case = {field["official_case"]: field["value"] for field in sheet["liasse"]["fields"]}
    assert by_case["217"] == "1000.00"
    assert by_case["264"] == "0.00"
    assert by_case["294"] == "80.00"
    assert by_case["350"] == "0.00"
    assert by_case["352"] == "920.00"
    assert by_case["370"] == "920.00"
    assert by_case["372"] == "0.00"
    assert by_case["420"] == "0.00"
    assert by_case["430"] == "0.00"
    assert "410" not in by_case
    assert not {"860", "870", "982"} & set(by_case)
    assert sheet["declarable"] is False
    assert sheet["status"] == "research_only"
    assert sheet["output_status"] == "recherche"
    assert sheet["output_label"] == "Recherche"
    assert sheet["copy_complete"] is True
    assert "prête à recopier" not in sheet["disclaimer"].casefold()
    by_code = {field["code"]: field["value"] for field in sheet["liasse"]["fields"]}
    assert by_code["2031_BIC_NON_PRO_BENEFICE"] == "920.00"
    assert by_code["2031BIS_LMNP_BENEFICE"] == "920.00"
    assert by_code["2031BIS_LMNP_DEFICIT"] == "0.00"
    personal = {line["case"]: line["amount"] for line in sheet["personal_return"]["lines"]}
    assert personal == {"5NA": "920.00", "5NY": "0.00"}
    assert any("018" in item for item in sheet["instructions"])
    pdf = client.get("/api/filing/years/1/efi.pdf")
    assert pdf.status_code == 200
    assert "Case 5NA".encode("cp1252") in pdf.content
    assert "2033-B — compte de résultat".encode("cp1252") in pdf.content
    assert "Avertissements".encode("cp1252") in pdf.content
    assert "Information".encode("cp1252") in pdf.content
    levels = {item["level"] for item in sheet["warnings"]}
    assert levels <= {"info", "warning", "error"}
    assert "info" in levels
    assert all(item["message"] for item in sheet["warnings"])


def test_2026_purchase_skips_the_2025_return(client):
    identify(client)
    created = client.post(
        "/api/ledger/years",
        json={
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "fiscal_vintage": "2026",
        },
    )
    assert created.status_code == 201, created.text
    year_id = next(row["id"] for row in created.json()["years"] if row["year"] == 2026)
    fiscal = client.post(f"/api/fiscal/years/{year_id}", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    sheet = client.get(f"/api/filing/years/{year_id}/efi").json()
    assert sheet["declarable"] is False
    assert sheet["output_status"] == "recherche"
    assert sheet["copy_complete"] is True
    assert "prête à recopier" not in sheet["disclaimer"].casefold()
    assert "millésime 2027" in sheet["vintage_note"]
    assert sheet["exercise"] == {"start": "2026-01-01", "end": "2026-12-31"}
    assert "Aucun envoi" in sheet["disclaimer"]


def _xlsx_text(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as bundle:
        return "\n".join(
            bundle.read(name).decode("utf-8", "replace")
            for name in bundle.namelist()
            if name.endswith(".xml")
        )


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
    "rules_version": "research-1",
}


def test_research_calculation_and_exports_hide_the_ready_phrase(client):
    book(client, "512000", "706000", "1000.00")
    book(client, "661000", "512000", "80.00")
    fiscal = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    body = fiscal.json()
    assert body["status"] == "research_only"
    assert body["output_status"] == "recherche"
    assert body["output_label"] == "Recherche"
    assert body["declarable"] is False
    identify(client)
    sheet = client.get("/api/filing/years/1/efi").json()
    assert sheet["output_status"] == "recherche"
    assert sheet["copy_complete"] is True
    assert sheet["declarable"] is False
    assert sheet["exports"]["liasse"]["posture"] == "provisoire"
    assert sheet["exports"]["fec"]["posture"] == "bloquee"
    assert "prête à recopier" not in sheet["disclaimer"].casefold()
    assert "prête à recopier" not in sheet["output_headline"].casefold()
    pdf = client.get("/api/filing/years/1/efi.pdf")
    assert b"Recherche" in pdf.content
    assert b"pr\xeate \xe0 recopier" not in pdf.content.lower()
    workbook = _xlsx_text(client.get("/api/filing/years/1/export.xlsx").content)
    assert "Recherche" in workbook
    assert "prête à recopier" not in workbook.casefold()
    precheck = client.get("/api/filing/years/1/precheck").json()
    assert precheck["output_status"] == "recherche"
    assert precheck["output_label"] == "Recherche"
    assert "FISCAL_RESEARCH" in {item["code"] for item in precheck["warnings"]}
    vintages = client.get("/api/fiscal/vintages").json()
    assert vintages["output_label"] == "Recherche"
    assert {row["output_status"] for row in vintages["vintages"]} == {"recherche"}


def test_validated_record_distinguishes_provisional_and_declarable(client, monkeypatch):
    holder = {"record": json.loads(json.dumps(VALIDATED))}

    def _load(vintage: str) -> dict[str, Any]:
        if vintage == "2025":
            return holder["record"]
        return {
            "vintage": vintage,
            "status": "research_only",
            "declarable": False,
            "version": None,
            "official_source": None,
            "validated_on": None,
            "scope": None,
            "rules_version": None,
        }

    monkeypatch.setattr("app.domain.fiscal.output_status.load_validation", _load)
    book(client, "512000", "706000", "1000.00")
    book(client, "661000", "512000", "80.00")
    created = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert created.status_code == 200, created.text
    assert created.json()["output_status"] == "declarable"
    assert created.json()["declarable"] is True
    blocked = client.get("/api/filing/years/1/efi").json()
    assert blocked["output_status"] == "provisoire"
    assert blocked["copy_complete"] is False
    assert blocked["declarable"] is False
    assert blocked["exports"]["liasse"]["posture"] == "bloquee"
    assert "prête à recopier" not in blocked["output_headline"].casefold()
    blocked_pdf = client.get("/api/filing/years/1/efi.pdf")
    assert blocked_pdf.status_code == 409
    detail = blocked_pdf.json()["detail"]
    assert detail["code"] in {"SIREN_MANQUANT", "EXPORT_BLOCKED"}
    assert detail["action"]["href"].endswith("#identite-liasse")
    blob = detail["message"] + " ".join(item["message"] for item in detail.get("issues") or [])
    assert "SIREN" in blob
    precheck = client.get("/api/filing/years/1/precheck").json()
    assert precheck["output_status"] == "provisoire"
    codes = {item["code"] for item in precheck["warnings"]}
    assert "FISCAL_PROVISOIRE" in codes
    assert "FISCAL_RESEARCH" not in codes

    identify(client)
    ready = client.get("/api/filing/years/1/efi").json()
    assert ready["output_status"] == "declarable"
    assert ready["output_label"] == "Déclarable"
    assert ready["declarable"] is True
    assert ready["copy_complete"] is True
    assert "Prête à recopier" in ready["output_headline"]
    assert ready["exports"]["liasse"]["posture"] == "provisoire"
    assert ready["exports"]["fec"]["posture"] == "bloquee"
    assert b"Pr\xeate \xe0 recopier" in client.get("/api/filing/years/1/efi.pdf").content
    ready_book = _xlsx_text(client.get("/api/filing/years/1/export.xlsx").content)
    assert "Déclarable — Prête à recopier" in ready_book

    holder["record"] = {**VALIDATED, "rules_version": "research-0"}
    stale = client.get("/api/filing/years/1/efi").json()
    assert stale["output_status"] == "provisoire"
    assert stale["copy_complete"] is True
    assert stale["declarable"] is False
    assert "prête à recopier" not in stale["output_headline"].casefold()
    assert client.get("/api/fiscal/years/1").json()["output_status"] == "provisoire"
