"""Fictional end-to-end checks for roadmap scenarios A to J."""

import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.domain.filing.fec import render_fec
from tests.integration.test_assets import furniture
from tests.integration.test_opening import next_year
from tests.integration.test_operations import client as seeded_client  # noqa: F401
from tests.integration.test_operations import loan, settlement
from tests.integration.test_statements import book, report

ROOT = Path(__file__).parents[2]


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


def _queries(engine, callback):
    count = 0

    def before(*_args):
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", before)
    try:
        callback()
    finally:
        event.remove(engine, "before_cursor_execute", before)
    return count


def test_scenarios_cover_the_fictional_catalogue(client):
    catalogue = json.loads((ROOT / "tests/fixtures/scenarios.json").read_text(encoding="utf-8"))
    required = {item for scenario in catalogue["scenarios"] for item in scenario["assertions"]}
    proven: set[str] = set()
    identity = client.post("/api/ledger/activity/identity", json={"siren": "123456789"})
    assert identity.status_code == 200, identity.text

    book(client, "512000", "108000", "1000.00")
    book(client, "512000", "706000", "100.00")
    book(client, "615000", "401000", "150.00")
    book(client, "681100", "281840", "20.00")
    opening_count = client.get("/api/ledger/entries?fiscal_year_id=1&source=OPENING").json()
    assert opening_count["count"] == 0
    proven.add("opening_balances_explicit")
    before = report(client)
    assert before["balance_sheet"]["balanced"] is True
    proven.add("balanced_ledger")

    assert client.post("/api/assets", json=furniture()).status_code == 201
    periods = client.post("/api/assets/years/1/calculate").json()
    row = periods[0]
    assert row["days"] == 184
    assert Decimal(row["amount"]) < Decimal("1200.00")
    assert Decimal(row["accumulated"]) <= Decimal(row["base"])
    assert Decimal(row["net_book_value"]) >= 0
    posted = client.post(
        f"/api/assets/periods/{periods[0]['id']}/post",
        json={"request_id": "depreciation-scenario", "piece_reference": "DOT-E"},
    )
    assert posted.status_code == 201, posted.text
    proven.update({"prorata_applied", "cumulative_not_above_base"})

    loan(client)
    assert (
        client.post("/api/operations/loans/1/fund", json=settlement(amount="10000.00")).status_code
        == 201
    )
    payment = client.post(
        "/api/operations/loans/1/payments",
        json=settlement(
            request_id="scenario-payment",
            date="2025-02-03",
            amount="125.00",
            principal="100.00",
            interest="20.00",
            insurance="5.00",
            other_costs="0.00",
        ),
    )
    assert payment.status_code == 201, payment.text
    entry = client.get(f"/api/ledger/entries/{payment.json()['accounting_entry_id']}").json()
    accounts = {line["account_number"] for line in entry["lines"]}
    assert {"164000", "661000", "616000"} <= accounts
    assert "706000" not in accounts
    proven.update({"principal_not_expense", "interest_insurance_separate"})

    depreciation_before = next(
        row["amount"]
        for row in report(client)["income_statement"]["expenses"]
        if row["account_number"] == "681100"
    )
    adjustment = {
        "account_number": "615000",
        "amount": "10.00",
        "justification": "Quote-part non déductible confirmée pour le scénario.",
    }
    fiscal = client.post("/api/fiscal/years/1", json={"adjustments": [adjustment]}).json()
    assert fiscal["status"] == "research_only" and fiscal["declarable"] is False
    assert (
        next(
            row["amount"]
            for row in report(client)["income_statement"]["expenses"]
            if row["account_number"] == "681100"
        )
        == depreciation_before
    )
    proven.add("accounting_depreciation_unchanged")
    assert fiscal["unused_depreciation"] != "0.00"
    assert fiscal["tax_loss"] != "0.00"
    assert fiscal["unused_depreciation"] != fiscal["tax_loss"]
    proven.update({"unused_depreciation_separate", "tax_loss_separate_from_depreciation"})
    expense_615 = next(
        row["amount"]
        for row in report(client)["income_statement"]["expenses"]
        if row["account_number"] == "615000"
    )
    assert expense_615 == "150.00"
    assert fiscal["non_deductible"] == "10.00"
    proven.update({"full_amount_in_ledger", "fiscal_addition_visible"})

    statements = report(client)
    result = statements["income_statement"]["result"]
    result_account = "129000" if result.startswith("-") else "120000"
    central = client.post(
        "/api/ledger/years/1/centralization",
        json={
            "request_id": str(uuid4()),
            "journal_code": "OD",
            "piece_reference": "CENT-J",
            "justification": "Centralisation du scénario fictif avant clôture.",
            "result_account": result_account,
            "expected_result": result,
        },
    )
    assert central.status_code == 200, central.text
    recomputed = client.post("/api/fiscal/years/1", json={"adjustments": [adjustment]})
    assert recomputed.status_code == 200, recomputed.text
    preview = client.get("/api/filing/years/1/precheck").json()
    assert preview["blocking"] is False, preview
    codes = [item["code"] for item in preview["warnings"]]
    assert client.post("/api/filing/years/1/ready", json={"acknowledged": codes}).status_code == 200
    closed = client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 200, closed.text
    assert book_rejected(client)
    proven.add("closed_locked")

    next_year(client)
    opening_preview = client.get("/api/ledger/years/2/opening-preview")
    assert opening_preview.status_code == 200, opening_preview.text
    generated = client.post(
        "/api/ledger/years/2/opening",
        json={
            "preview_token": opening_preview.json()["preview_token"],
            "journal_code": "AN",
            "piece_reference": "AN-2026",
            "result_account": None,
        },
    )
    assert generated.status_code == 200, generated.text
    continuity = client.get("/api/ledger/years/2/opening-continuity").json()
    assert continuity["balances_match"] is True
    proven.add("prior_closing_equals_opening")
    year_two = client.post("/api/fiscal/years/2", json={"adjustments": []}).json()
    assert year_two["vintage"] == "2026"
    assert year_two["rules_sha256"] != recomputed.json()["rules_sha256"]
    proven.add("vintage_isolated")

    fec_one = client.get("/api/filing/years/1/fec")
    fec_two = client.get("/api/filing/years/1/fec")
    assert fec_one.status_code == 200
    assert fec_one.content == fec_two.content
    assert fec_one.headers["x-content-sha256"] == fec_two.headers["x-content-sha256"]
    header = fec_one.content.split(b"\r\n", 1)[0].decode()
    assert header.count("\t") == 17
    proven.update({"ledger_only", "deterministic", "validator_no_error"})

    package = client.get("/api/filing/years/1/package").json()
    assert package["errors"] == []
    assert package["fields"]
    assert all(
        field["expression"] and field["accounts"] is not None and field["entries"] is not None
        for field in package["fields"]
    )
    assert all(field["status"] == "research_only" for field in package["fields"])
    proven.add("field_traceability")
    assert not any(item["code"] == "INTERFORM" for item in package["errors"])
    proven.add("interform_checks")
    efi = client.get("/api/filing/years/1/efi").json()
    assert efi["transmission"] is False
    assert efi["personal_return"]["separated_from_liasse"] is True
    proven.add("efi_not_transmission")

    missing = client.post(
        "/api/filing/years/1/reopen",
        json={"confirmation": "ROUVRIR", "reason": "court"},
    )
    assert missing.status_code == 422
    proven.add("reason_required")
    reopened = client.post(
        "/api/filing/years/1/reopen",
        json={"confirmation": "ROUVRIR", "reason": "Réouverture motivée du scénario fictif."},
    )
    assert reopened.status_code == 200, reopened.text
    assert client.get("/api/filing/years/1/efi").status_code == 404
    proven.add("snapshot_superseded")
    assert required <= proven


def book_rejected(client) -> bool:
    response = client.post(
        "/api/ledger/entries",
        json={
            "fiscal_year_id": 1,
            "journal_code": "BQ",
            "accounting_date": "2025-03-01",
            "piece_reference": "LOCKED",
            "piece_date": "2025-03-01",
            "label": "Écriture après clôture",
            "lines": [
                {"account_number": "512000", "label": "Banque", "debit": "1.00", "credit": "0.00"},
                {"account_number": "706000", "label": "Produit", "debit": "0.00", "credit": "1.00"},
            ],
        },
    )
    return response.status_code == 409


def test_read_paths_stay_within_query_budgets(client):
    book(client, "512000", "706000", "10.00")
    engine = client.app.state.database.engine
    journal = _queries(engine, lambda: client.get("/api/ledger/entries?fiscal_year_id=1"))
    statements = _queries(engine, lambda: client.get("/api/ledger/years/1/statements"))

    def render():
        session = client.app.state.database.sessions()
        try:
            render_fec(session, 1)
        finally:
            session.close()

    fec = _queries(engine, render)
    assert journal <= 40, journal
    assert statements <= 40, statements
    assert fec <= 40, fec
