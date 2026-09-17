import pytest

from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_ledger import draft, payload, post
from tests.integration.test_statements import book, report


@pytest.fixture
def client(seeded_client):  # noqa: F811
    return seeded_client


def next_year(client, start="2026-01-01"):
    response = client.post(
        "/api/ledger/years",
        json={
            "year": 2026,
            "start_date": start,
            "end_date": "2026-12-31",
            "fiscal_vintage": "2026",
        },
    )
    assert response.status_code == 201, response.text


def preview(client):
    response = client.get("/api/ledger/years/2/opening-preview")
    assert response.status_code == 200, response.text
    return response.json()


def codes(value):
    return {warning["code"] for warning in value["warnings"]}


def test_profit_preview_preserves_balances_without_writes(client):
    book(client, "512000", "108000", "2000.00")
    book(client, "218400", "512000", "1200.00")
    book(client, "411000", "706000", "900.25")
    book(client, "615000", "401000", "100.15")
    book(client, "681100", "281840", "200.00")
    draft(client)
    next_year(client)
    before = report(client)
    value = preview(client)
    rows = {row["account_number"]: row for row in value["lines"]}
    assert set(rows) == {"108000", "218400", "281840", "401000", "411000", "512000"}
    assert rows["281840"]["credit"] == "200.00"
    assert rows["411000"]["debit"] == "900.25"
    assert value["previous_result"] == value["result_line"]["credit"] == "600.10"
    assert value["result_line"]["account_number"] is None
    assert value["total_debit"] == value["total_credit"] == "2900.25"
    assert value["status"] == "PROVISIONAL" and value["read_only"] is True
    assert {"SOURCE_NOT_CLOSED", "SOURCE_DRAFTS", "RESULT_ACCOUNT_REQUIRED"} <= codes(value)
    assert value["excluded_draft_count"] == 1
    assert preview(client) == value
    assert report(client) == before
    assert report(client, 2)["balance_sheet"]["assets"] == []
    assert client.get("/api/ledger/entries?fiscal_year_id=2").json()["count"] == 0


@pytest.mark.parametrize("loss", [False, True])
def test_profit_and_loss_use_exact_cents(client, loss):
    for amount in ("0.01", "0.02", "100000000.99"):
        book(client, "615000" if loss else "512000", "401000" if loss else "706000", amount)
    next_year(client)
    value = preview(client)
    assert value["result_line"]["debit" if loss else "credit"] == "100000001.02"
    assert value["total_debit"] == value["total_credit"] == "100000001.02"


def test_zero_result_and_settled_accounts_are_omitted(client):
    entry = book(client, "512000", "706000", "10.00")
    assert (
        client.post(
            f"/api/ledger/entries/{entry['id']}/reverse",
            json={
                "accounting_date": "2025-02-02",
                "piece_reference": "EXT",
                "reason": "Correction",
            },
        ).status_code
        == 201
    )
    next_year(client)
    value = preview(client)
    assert value["lines"] == [] and value["result_line"] is None
    assert value["total_debit"] == value["total_credit"] == "0.00"


@pytest.mark.parametrize("loss", [False, True])
def test_aggregate_balances_can_exceed_individual_storage_limit(client, loss):
    for _ in range(2):
        book(
            client,
            "615000" if loss else "512000",
            "401000" if loss else "706000",
            "92233720368547758.07",
        )
    next_year(client)
    value = preview(client)
    assert value["total_debit"] == value["total_credit"] == "184467440737095516.14"
    assert value["result_line"]["debit" if loss else "credit"] == "184467440737095516.14"


def test_requires_immediately_adjacent_previous_year(client):
    assert client.get("/api/ledger/years/999/opening-preview").status_code == 404
    assert (
        client.get("/api/ledger/years/1/opening-preview").json()["detail"]["code"]
        == "PREVIOUS_YEAR_REQUIRED"
    )
    next_year(client, "2026-02-01")
    assert client.get("/api/ledger/years/2/opening-preview").status_code == 409


def test_inactive_balances_and_existing_target_entries_are_flagged(client):
    book(client, "512000", "108000", "10.00")
    next_year(client)
    data = payload()
    data.update(fiscal_year_id=2, accounting_date="2026-01-01", piece_date="2026-01-01")
    entry = draft(client, data)
    assert post(client, entry).status_code == 200
    assert (
        client.patch("/api/ledger/accounts/108000/active", json={"active": False}).status_code
        == 200
    )
    value = preview(client)
    assert {"INACTIVE_ACCOUNTS", "TARGET_HAS_ENTRIES"} <= codes(value)
    assert value["target_entry_count"] == 1
    assert value["previous_result"] == "0.00"
    assert report(client, 2)["income_statement"]["result"] == "123.45"


def test_invalid_classification_blocks_preview(client):
    assert (
        client.post(
            "/api/ledger/accounts",
            json={"number": "699000", "label": "Incohérent", "account_type": "ASSET"},
        ).status_code
        == 201
    )
    book(client, "699000", "512000", "1.00")
    next_year(client)
    response = client.get("/api/ledger/years/2/opening-preview")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INVALID_STATEMENT_ACCOUNT"


def test_closed_source_and_locked_target_remain_provisional(client, database):
    from datetime import datetime

    from app.models import FiscalYear

    next_year(client)
    with database.sessions.begin() as session:
        source = session.get(FiscalYear, 1)
        target = session.get(FiscalYear, 2)
        source.status = "CLOSED"
        source.closed_at = datetime(2026, 1, 1)
        target.status = "READY_TO_CLOSE"
    value = preview(client)
    assert value["status"] == "PROVISIONAL"
    assert codes(value) == {"PREVIEW_ONLY", "TARGET_NOT_OPEN"}
    assert value["lines"] == []


def test_corrupt_source_is_blocked(client):
    from decimal import Decimal

    from sqlalchemy import event

    from app.models import AccountingEntryLine

    book(client, "512000", "706000", "10.00")
    next_year(client)

    def corrupt(line, context):
        if line.account_number == "512000":
            line.debit = Decimal("10.01")

    event.listen(AccountingEntryLine, "load", corrupt)
    try:
        response = client.get("/api/ledger/years/2/opening-preview")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "UNBALANCED_STATEMENTS"
    finally:
        event.remove(AccountingEntryLine, "load", corrupt)
