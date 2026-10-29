"""First LMNP exercise: property bought before the rental start, two loans, closing, FEC.

Dated one year back from the real 2026 case: SQLite refuses postings dated in the future.
"""

import io
import zipfile
from uuid import uuid4
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

SIREN = "123456789"


@pytest.fixture
def client(settings, database):
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as client:
        steps = [
            (
                "/api/ledger/activity",
                {"activity_name": "Mérignac", "activity_start_date": "2025-04-06"},
            ),
            (
                "/api/ledger/years",
                {
                    "year": 2025,
                    "start_date": "2025-04-06",
                    "end_date": "2025-12-31",
                    "fiscal_vintage": "2025",
                },
            ),
            (
                "/api/operations/properties",
                {
                    "name": "Mérignac 1",
                    "address": "11 rue fictive",
                    "acquisition_date": "2025-01-09",
                    "rental_start_date": "2025-04-06",
                    "acquisition_price": "145000.00",
                    "acquisition_costs": "18262.00",
                    "land_value": "29000.00",
                    "building_value": "116000.00",
                },
            ),
            ("/api/operations/banks", {"name": "Banque", "account_number": "512000"}),
        ]
        for path, body in steps:
            response = client.post(path, json=body)
            assert response.status_code == 201, response.text
        for principal in ("15000.00", "195000.00"):
            response = client.post(
                "/api/operations/loans",
                json={
                    "property_id": 1,
                    "lender": "Banque prêteuse",
                    "start_date": "2025-01-09",
                    "initial_principal": principal,
                    "interest_rate": "3.25",
                    "duration_months": 300,
                },
            )
            assert response.status_code == 201, response.text
        for number, label in (("120000", "Résultat bénéfice"), ("129000", "Résultat perte")):
            response = client.post(
                "/api/ledger/accounts",
                json={"number": number, "label": label, "account_type": "EQUITY"},
            )
            assert response.status_code == 201, response.text
        yield client


def operation(client, kind, day, amount, account, label):
    response = client.post(
        "/api/operations",
        json={
            "request_id": f"op-{uuid4().hex[:20]}",
            "kind": kind,
            "property_id": 1,
            "fiscal_year_id": 1,
            "date": day,
            "piece_date": day,
            "piece_reference": f"{label[:20]}-{day}",
            "amount": amount,
            "description": label,
            "counterparty": "Locataire" if kind == "REVENUE" else "Fournisseur",
            "accounting_account": account,
            "bank_account_id": 1,
        },
    )
    assert response.status_code == 201, response.text


def loan_payment(client, loan_id, day, principal, interest):
    total = f"{float(principal) + float(interest):.2f}"
    response = client.post(
        f"/api/operations/loans/{loan_id}/payments",
        json={
            "request_id": f"pay-{uuid4().hex[:20]}",
            "fiscal_year_id": 1,
            "date": day,
            "piece_reference": f"ECH-{loan_id}-{day}",
            "amount": total,
            "bank_account_id": 1,
            "principal": principal,
            "interest": interest,
            "insurance": "0.00",
            "other_costs": "0.00",
        },
    )
    assert response.status_code == 201, response.text


def test_first_exercise_from_purchase_to_liasse_and_fec(client):
    preview = client.get("/api/assets/properties/1/plan")
    assert preview.status_code == 200, preview.text
    assert preview.json()["created"] is False
    plan = client.post(
        "/api/assets/properties/1/plan",
        json={"confirm": True, "preview_token": preview.json()["preview_token"]},
    )
    assert plan.status_code == 201, plan.text
    assert plan.json()["created"] is True
    assert plan.json()["items"] == preview.json()["items"]
    assert plan.json()["depreciable_base"] == "134262.00"

    entry = {
        "fiscal_year_id": 1,
        "loans": [
            {"loan_id": 1, "outstanding": "14884.00"},
            {"loan_id": 2, "outstanding": "195000.00"},
        ],
        "bank_account_id": 1,
        "bank_amount": "46000.00",
        "prior_charges": [
            {
                "account_number": "661000",
                "amount": "1200.00",
                "label": "Intérêts payés avant la mise en location",
            },
            {"account_number": "627000", "amount": "500.00", "label": "Frais de dossier"},
        ],
        "piece_reference": "ACTE-2025-01-09",
    }
    preview = client.post("/api/assets/properties/1/entry", json=entry)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["posted"] is False
    assert body["accounting_date"] == "2025-04-06"
    assert body["piece_date"] == "2025-01-09"
    debit = sum(float(line["debit"]) for line in body["lines"])
    credit = sum(float(line["credit"]) for line in body["lines"])
    assert round(debit, 2) == round(credit, 2)
    # 29 000 + 134 262 + 46 000 + 1 700 - 14 884 - 195 000 = 1 078 € apportés par l'exploitant.
    assert body["owner_contribution"] == "1078.00"
    posted = client.post("/api/assets/properties/1/entry", json={**entry, "confirm": True})
    assert posted.status_code == 200, posted.text
    again = client.post("/api/assets/properties/1/entry", json={**entry, "confirm": True})
    assert again.status_code == 409
    funding = client.post(
        "/api/operations/loans/2/fund",
        json={
            "request_id": f"fund-{uuid4().hex[:20]}",
            "fiscal_year_id": 1,
            "date": "2025-04-06",
            "piece_reference": "FUND",
            "amount": "195000.00",
            "bank_account_id": 1,
        },
    )
    assert funding.status_code == 409

    for month in range(4, 13):
        operation(client, "REVENUE", f"2025-{month:02d}-06", "850.00", "706000", "Loyer")
    operation(client, "EXPENSE", "2025-10-15", "900.00", "635000", "Taxe foncière")
    operation(client, "EXPENSE", "2025-05-02", "180.00", "616000", "Assurance PNO")
    operation(client, "EXPENSE", "2025-07-01", "1200.00", "614000", "Charges de copropriété")
    for day in ("2025-05-09", "2025-06-09"):
        loan_payment(client, 1, day, "40.00", "18.00")
        loan_payment(client, 2, day, "0.00", "528.00")

    calculated = client.post("/api/assets/years/1/calculate")
    assert calculated.status_code == 200, calculated.text
    for period in calculated.json():
        response = client.post(
            f"/api/assets/periods/{period['id']}/post",
            json={"request_id": f"dot-{period['id']}-2025", "piece_reference": "DOT-2025"},
        )
        assert response.status_code == 201, response.text

    statements = client.get("/api/ledger/years/1/statements").json()
    result = statements["income_statement"]["result"]
    centralized = client.post(
        "/api/ledger/years/1/centralization",
        json={
            "request_id": str(uuid4()),
            "journal_code": "OD",
            "piece_reference": "CENT-2025",
            "justification": "Centralisation de clôture du premier exercice.",
            "result_account": "129000" if result.startswith("-") else "120000",
            "expected_result": result,
        },
    )
    assert centralized.status_code == 200, centralized.text
    fiscal = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    computed = fiscal.json()
    assert computed["fiscal_result"] == "0.00"
    assert computed["details"]["capacity"] == "2578.00"
    assert computed["unused_depreciation"] != "0.00"

    sheet = client.get("/api/filing/years/1/efi").json()
    assert [item["code"] for item in sheet["blocking"]] == ["SIREN_MANQUANT"]
    assert client.post("/api/ledger/activity/identity", json={"siren": SIREN}).status_code == 200

    precheck = client.get("/api/filing/years/1/precheck").json()
    assert precheck["blocking"] is False, precheck
    codes = [item["code"] for item in precheck["warnings"]]
    assert "IMMOBILISATIONS_ECART" not in codes
    ready = client.post("/api/filing/years/1/ready", json={"acknowledged": codes})
    assert ready.status_code == 200, ready.text
    closed = client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 200, closed.text

    sheet = client.get("/api/filing/years/1/efi").json()
    assert sheet["frozen"] is True
    assert sheet["declarable"] is True, sheet["blocking"]
    assert sheet["status"] == "ready"
    assert sheet["exercise"] == {"start": "2025-04-06", "end": "2025-12-31"}
    by_case = {field["official_case"]: field["value"] for field in sheet["liasse"]["fields"]}
    assert by_case["217"] == "7650.00"
    assert by_case["108"] == "7650.00"
    assert by_case["420"] == "0.00"
    assert by_case["422"] == "29000.00"
    assert by_case["426"] == "29000.00"
    assert by_case["490"] == "0.00"
    assert by_case["492"] == "163262.00"
    assert by_case["318"] == computed["unused_depreciation"]
    assert by_case["352"] == by_case["370"] == "0.00"
    assert by_case["354"] == by_case["372"] == "0.00"
    assert by_case["156"] == "209804.00"
    assert by_case["112"] == by_case["180"]
    personal = {line["case"]: line["amount"] for line in sheet["personal_return"]["lines"]}
    assert personal == {"5NA": "0.00", "5NY": "0.00"}
    tracking = sheet["depreciation_tracking"]
    assert tracking["deferred_current"] == computed["unused_depreciation"]
    assert tracking["remaining_total"] == computed["unused_depreciation"]

    fec = client.get("/api/filing/years/1/fec")
    assert fec.status_code == 200, fec.text
    assert f'filename="{SIREN}FEC20251231.txt"' in fec.headers["content-disposition"]
    text = fec.content.decode("utf-8")
    assert "\t108000\t" in text and "\t164001\t" in text and "\t213000\t" in text
    assert "\tCENT-2025\t" not in text
    archive = client.get("/api/filing/years/1/archive")
    assert archive.status_code == 200, archive.text
    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        assert bundle.read(f"{SIREN}FEC20251231.txt") == fec.content
        pdf = bundle.read("liasse-2025.pdf")
        assert "Case 318".encode("cp1252") in pdf
        assert "État de suivi des amortissements".encode("cp1252") in pdf

    workbook = client.get("/api/filing/years/1/export.xlsx")
    assert workbook.status_code == 200, workbook.text
    assert 'filename="SoloLMNP-2025.xlsx"' in workbook.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(workbook.content)) as bundle:
        sheets = [name for name in bundle.namelist() if name.startswith("xl/worksheets/")]
        assert len(sheets) == 5
        for name in bundle.namelist():
            if name.endswith(".xml") or name.endswith(".rels"):
                ElementTree.fromstring(bundle.read(name))  # noqa: S314 - XML produced by the app
        assert "Mérignac" in bundle.read("xl/worksheets/sheet1.xml").decode()
        assert "<v>7650.00</v>" not in bundle.read("xl/worksheets/sheet1.xml").decode()
        assert "Case" in bundle.read("xl/worksheets/sheet5.xml").decode()
        assert "Gros œuvre" in bundle.read("xl/worksheets/sheet4.xml").decode()
