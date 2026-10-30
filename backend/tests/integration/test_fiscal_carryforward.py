"""Golden multi-year checks for FIFO consumption of prior fiscal carry-forwards."""

from uuid import uuid4

import pytest

from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_ledger import draft, payload, post
from tests.integration.test_opening import next_year
from tests.integration.test_statements import book, report


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


def _centralize(client, year_id: int, result: str) -> None:
    account = "120000" if not result.startswith("-") else "129000"
    response = client.post(
        f"/api/ledger/years/{year_id}/centralization",
        json={
            "request_id": str(uuid4()),
            "journal_code": "OD",
            "piece_reference": f"CENT-{year_id}",
            "justification": "Centralisation de test avant clôture fiscale.",
            "result_account": account,
            "expected_result": result,
        },
    )
    assert response.status_code == 200, response.text


def _close_after_fiscal(client, year_id: int) -> dict:
    """Centralize, compute fiscal on the final ledger, then close."""
    result = report(client, year_id)["income_statement"]["result"]
    _centralize(client, year_id, result)
    fiscal = client.post(f"/api/fiscal/years/{year_id}", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    preview = client.get(f"/api/filing/years/{year_id}/precheck")
    assert preview.status_code == 200, preview.text
    assert preview.json()["blocking"] is False, preview.text
    codes = [item["code"] for item in preview.json()["warnings"]]
    assert (
        client.post(f"/api/filing/years/{year_id}/ready", json={"acknowledged": codes}).status_code
        == 200
    )
    closed = client.post(f"/api/filing/years/{year_id}/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 200, closed.text
    return fiscal.json()


def _book_year_two(client, debit: str, credit: str, amount: str) -> None:
    data = payload()
    data.update(
        fiscal_year_id=2,
        accounting_date="2026-03-01",
        piece_date="2026-03-01",
        piece_reference=f"Y2-{debit}-{credit}-{amount}",
        label="Écriture exercice N+1",
    )
    data["lines"] = [
        {"account_number": debit, "label": debit, "debit": amount, "credit": "0.00"},
        {"account_number": credit, "label": credit, "debit": "0.00", "credit": amount},
    ]
    assert post(client, draft(client, data)).status_code == 200


def test_prior_unused_depreciation_is_consumed_fifo_on_capacity(client):
    # N : loyers 1000, charges 400, dotation 800 → capacité 600, non déduit 200, résultat fiscal 0
    book(client, "512000", "706000", "1000.00")
    book(client, "615000", "401000", "400.00")
    book(client, "681100", "281840", "800.00")
    preview = client.post("/api/fiscal/years/1", json={"adjustments": []}).json()
    assert preview["deductible_depreciation"] == "600.00"
    assert preview["unused_depreciation"] == "200.00"
    assert preview["fiscal_result"] == "0.00"
    assert preview["details"]["prior_carry_forward_use"]["status"] == "enabled"
    assert preview["details"]["prior_carry_forward_use"]["depreciation"] == []
    closed_fiscal = _close_after_fiscal(client, 1)
    assert closed_fiscal["unused_depreciation"] == "200.00"

    next_year(client)
    # N+1 : loyers 1000, charges 200, dotation 100 → capacité 800 ; consomme les 200 reportés
    _book_year_two(client, "512000", "706000", "1000.00")
    _book_year_two(client, "615000", "401000", "200.00")
    _book_year_two(client, "681100", "281840", "100.00")
    year_two = client.post("/api/fiscal/years/2", json={"adjustments": []}).json()
    assert year_two["status"] == "research_only"
    assert year_two["declarable"] is False
    assert year_two["details"]["current_deductible_depreciation"] == "100.00"
    assert year_two["details"]["prior_depreciation_used"] == "200.00"
    assert year_two["deductible_depreciation"] == "300.00"
    assert year_two["unused_depreciation"] == "0.00"
    assert year_two["fiscal_result"] == "500.00"
    uses = year_two["details"]["prior_carry_forward_use"]["depreciation"]
    assert len(uses) == 1
    assert uses[0]["origin_year"] == 2025
    assert uses[0]["used"] == "200.00"
    assert uses[0]["remaining_after"] == "0.00"
    sheet = client.get("/api/filing/years/2/efi").json()
    by_case = {field["official_case"]: field["value"] for field in sheet["liasse"]["fields"]}
    assert by_case["318"] == "0.00"
    assert by_case["350"] == "200.00"
    assert by_case["352"] == "500.00"
    assert by_case["370"] == "500.00"
    assert not any(item["code"] == "INTERFORM" for item in sheet["blocking"])
    tracking = sheet["depreciation_tracking"]
    assert tracking["prior_used"] == "200.00"
    assert tracking["prior"] == [
        {"origin_year": 2025, "opening": "200.00", "used": "200.00", "remaining": "0.00"}
    ]
    assert tracking["remaining_total"] == "0.00"


def test_prior_tax_loss_is_consumed_fifo_without_global_income(client):
    # N : déficit fiscal 150, distinct de tout amortissement non déduit
    book(client, "512000", "706000", "100.00")
    book(client, "615000", "401000", "250.00")
    preview = client.post("/api/fiscal/years/1", json={"adjustments": []}).json()
    assert preview["fiscal_result"] == "-150.00"
    assert preview["tax_loss"] == "150.00"
    assert preview["unused_depreciation"] == "0.00"
    closed_fiscal = _close_after_fiscal(client, 1)
    assert closed_fiscal["tax_loss"] == "150.00"

    next_year(client)
    # N+1 : résultat fiscal avant reports 400 → impute 150, reste 250
    _book_year_two(client, "512000", "706000", "500.00")
    _book_year_two(client, "615000", "401000", "100.00")
    year_two = client.post("/api/fiscal/years/2", json={"adjustments": []}).json()
    assert year_two["details"]["fiscal_result_before_prior_losses"] == "400.00"
    assert year_two["details"]["prior_tax_loss_used"] == "150.00"
    assert year_two["fiscal_result"] == "250.00"
    assert year_two["tax_loss"] == "0.00"
    assert year_two["imputed_on_global_income"] == "0.00"
    uses = year_two["details"]["prior_carry_forward_use"]["tax_loss"]
    assert len(uses) == 1
    assert uses[0]["origin_year"] == 2025
    assert uses[0]["used"] == "150.00"
    assert uses[0]["remaining_after"] == "0.00"
    # La liasse IR n'impute pas les déficits antérieurs : ils vont sur la 2042-C-PRO.
    sheet = client.get("/api/filing/years/2/efi").json()
    by_case = {field["official_case"]: field["value"] for field in sheet["liasse"]["fields"]}
    assert by_case["352"] == "400.00"
    assert by_case["370"] == "400.00"
    assert not any(item["code"] == "INTERFORM" for item in sheet["blocking"])
    personal = sheet["personal_return"]
    assert {line["case"]: line["amount"] for line in personal["lines"]} == {
        "5NA": "400.00",
        "5NY": "0.00",
    }
    assert personal["prior_deficits"] == [{"origin_year": 2025, "case": "5GJ", "amount": "150.00"}]
    _book_year_two(client, "512000", "706000", "100.00")
    recomputed = client.post("/api/fiscal/years/2", json={"adjustments": []}).json()
    assert recomputed["replayed"] is False
    assert recomputed["id"] != year_two["id"]
    assert recomputed["details"]["prior_tax_loss_used"] == "150.00"
    assert recomputed["fiscal_result"] == "350.00"
    loss = recomputed["details"]["carry_registers"]["tax_loss"]
    origin = next(row for row in loss["rows"] if row["origin_year"] == 2025)
    assert origin == {
        "origin_year": 2025,
        "created": "150.00",
        "used": "150.00",
        "expired": "0.00",
        "remaining": "0.00",
    }
    reopened = client.post(
        "/api/filing/years/1/reopen",
        json={"confirmation": "ROUVRIR", "reason": "Corriger le déficit avant un nouveau calcul."},
    )
    assert reopened.status_code == 200, reopened.text
    after_reopen = client.post("/api/fiscal/years/2", json={"adjustments": []}).json()
    assert after_reopen["details"]["prior_tax_loss_used"] == "0.00"
    assert after_reopen["fiscal_result"] == "500.00"
    assert after_reopen["details"]["carry_registers"]["tax_loss"]["totals"]["used"] == "0.00"


def test_open_prior_year_is_not_consumed_until_closed(client):
    book(client, "512000", "706000", "100.00")
    book(client, "615000", "401000", "250.00")
    year_one = client.post("/api/fiscal/years/1", json={"adjustments": []}).json()
    assert year_one["tax_loss"] == "150.00"
    next_year(client)
    _book_year_two(client, "512000", "706000", "500.00")
    year_two = client.post("/api/fiscal/years/2", json={"adjustments": []}).json()
    assert year_two["details"]["prior_tax_loss_used"] == "0.00"
    assert year_two["details"]["prior_carry_forward_use"]["tax_loss"] == []
    assert year_two["fiscal_result"] == "500.00"
