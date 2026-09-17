from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import FiscalYear, LedgerEvent
from tests.integration.test_ledger import client as seeded_client  # noqa: F401
from tests.integration.test_ledger import draft, payload, post
from tests.integration.test_opening import next_year, preview
from tests.integration.test_statements import book, report


@pytest.fixture
def client(seeded_client):  # noqa: F811
    for number in ("120000", "129000", "120900"):
        assert (
            seeded_client.post(
                "/api/ledger/accounts",
                json={
                    "number": number,
                    "label": "Résultat fictif",
                    "account_type": "EQUITY",
                },
            ).status_code
            == 201
        )
    return seeded_client


def close(database, year_id=1):
    with database.sessions.begin() as session:
        source = session.get(FiscalYear, year_id)
        source.status = "CLOSED"
        source.closed_at = datetime(2026, 1, 1)


def request(client, result_account="120000"):
    return {
        "preview_token": preview(client)["preview_token"],
        "journal_code": "AN",
        "piece_reference": "AN-2026",
        "result_account": result_account,
    }


def generate(client, data):
    return client.post("/api/ledger/years/2/opening", json=data)


def continuity(client):
    response = client.get("/api/ledger/years/2/opening-continuity")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("loss", [False, True])
def test_posting_and_second_year_continuity(client, database, loss):
    book(client, "512000", "108000", "2000.00")
    book(client, "218400", "512000", "1200.00")
    book(client, "411000", "706000", "900.25")
    book(client, "615000", "401000", "1100.15" if loss else "100.15")
    book(client, "681100", "281840", "200.00")
    next_year(client)
    before = report(client)
    close(database)
    data = request(client, "129000" if loss else "120000")
    response = generate(client, data)
    assert response.status_code == 200, response.text
    entry = response.json()["entry"]
    assert response.json()["created"] is True
    assert entry["source_type"] == "OPENING" and entry["source_id"] == "1"
    assert entry["status"] == "VALIDATED" and entry["accounting_date"] == "2026-01-01"
    assert entry["total_debit"] == entry["total_credit"]
    assert not any(line["account_number"][0] in "67" for line in entry["lines"])
    assert report(client) == before
    opened = report(client, 2)
    assert opened["income_statement"]["result"] == "0.00"
    assert opened["balance_sheet"]["assets"] == before["balance_sheet"]["assets"]
    assert opened["balance_sheet"]["liabilities"] == before["balance_sheet"]["liabilities"]
    assert continuity(client)["balances_match"] is True
    # A second-year receipt settles the carried receivable without creating revenue.
    settlement = payload()
    settlement.update(fiscal_year_id=2, accounting_date="2026-01-02", piece_date="2026-01-02")
    settlement["lines"] = [
        {"account_number": "512000", "label": "Règlement", "debit": "900.25"},
        {"account_number": "411000", "label": "Créance reprise", "credit": "900.25"},
    ]
    assert post(client, draft(client, settlement)).status_code == 200
    assert report(client, 2)["income_statement"]["result"] == "0.00"
    assert continuity(client)["balances_match"] is True
    events = client.get(f"/api/ledger/entries/{entry['id']}/events").json()
    replay = generate(client, data)
    assert replay.json() == {"created": False, "entry": entry}
    assert client.get(f"/api/ledger/entries/{entry['id']}/events").json() == events
    assert generate(client, {**data, "piece_reference": "OTHER"}).status_code == 409
    assert (
        client.post(
            f"/api/ledger/entries/{entry['id']}/reverse",
            json={
                "accounting_date": "2026-01-02",
                "piece_reference": "EXT",
                "reason": "Correction",
            },
        ).json()["detail"]["code"]
        == "BUSINESS_REVERSAL_REQUIRED"
    )


def test_parallel_retries_create_one_entry_and_audit(client, database):
    book(client, "512000", "706000", "0.03")
    next_year(client)
    close(database)
    data = request(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: generate(client, data), range(2)))
    assert [response.status_code for response in results] == [200, 200]
    assert sorted(response.json()["created"] for response in results) == [False, True]
    assert len({response.json()["entry"]["id"] for response in results}) == 1
    with database.sessions() as session:
        assert (
            len(
                session.scalars(
                    select(LedgerEvent).where(LedgerEvent.action == "OPENING_GENERATED")
                ).all()
            )
            == 1
        )


@pytest.mark.parametrize(
    "case,code",
    [
        ("unclosed", "SOURCE_NOT_CLOSED"),
        ("drafts", "SOURCE_DRAFTS"),
        ("changed", "OPENING_PREVIEW_CHANGED"),
        ("occupied", "TARGET_HAS_ENTRIES"),
        ("locked", "YEAR_LOCKED"),
        ("inactive", "INACTIVE_ACCOUNT"),
        ("journal", "OPENING_JOURNAL_REQUIRED"),
        ("result", "INVALID_RESULT_ACCOUNT"),
        ("dividends", "INVALID_RESULT_ACCOUNT"),
        ("overflow", "OPENING_TOO_LARGE"),
    ],
)
def test_generation_guards_leave_no_partial_writes(client, database, case, code):
    book(client, "512000", "706000", "10.01")
    if case == "overflow":
        book(client, "512000", "706000", "92233720368547758.07")
    if case == "drafts":
        draft(client)
    next_year(client)
    data = request(client)
    if case == "changed":
        book(client, "512000", "706000", "1.00")
    if case != "unclosed":
        close(database)
    if case == "occupied":
        entry = payload()
        entry.update(fiscal_year_id=2, accounting_date="2026-01-01")
        draft(client, entry)
    if case == "locked":
        close(database, 2)
    if case == "inactive":
        client.patch("/api/ledger/accounts/512000/active", json={"active": False})
    if case == "journal":
        data["journal_code"] = "OD"
    if case in {"result", "dividends"}:
        data["result_account"] = "129000" if case == "result" else "120900"
    before = client.get("/api/ledger/entries?fiscal_year_id=2").json()
    with database.sessions() as session:
        audit_before = len(session.scalars(select(LedgerEvent)).all())
    response = generate(client, data)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == code
    assert client.get("/api/ledger/entries?fiscal_year_id=2").json() == before
    with database.sessions() as session:
        assert len(session.scalars(select(LedgerEvent)).all()) == audit_before


def test_zero_result_and_empty_opening(client, database):
    next_year(client)
    assert continuity(client)["reason"] == "OPENING_NOT_GENERATED"
    close(database)
    assert generate(client, request(client, None)).json()["detail"]["code"] == "EMPTY_OPENING"


def test_zero_result_replay_after_target_is_closed(client, database):
    book(client, "512000", "108000", "0.01")
    next_year(client)
    close(database)
    data = request(client, None)
    assert (
        generate(client, {**data, "result_account": "120000"}).json()["detail"]["code"]
        == "UNEXPECTED_RESULT_ACCOUNT"
    )
    response = generate(client, data)
    assert response.status_code == 200, response.text
    close(database, 2)
    assert generate(client, data).json()["entry"] == response.json()["entry"]


def test_post_failure_rolls_back_entry_and_events(client, database, monkeypatch):
    from app.services import opening_posting
    from app.services.ledger import fail

    book(client, "512000", "706000", "1.00")
    next_year(client)
    close(database)
    data = request(client)

    def refused(*args):
        fail("SIMULATED_FAILURE", "Validation refusée")

    monkeypatch.setattr(opening_posting, "post_entry", refused)
    assert generate(client, data).status_code == 409
    assert client.get("/api/ledger/entries?fiscal_year_id=2").json()["count"] == 0
    with database.sessions() as session:
        assert not session.scalars(
            select(LedgerEvent).where(LedgerEvent.action == "OPENING_GENERATED")
        ).all()


def test_continuity_detects_source_change_after_reopening(client, database):
    book(client, "512000", "706000", "10.00")
    next_year(client)
    close(database)
    data = request(client)
    assert generate(client, data).status_code == 200
    with database.sessions.begin() as session:
        source = session.get(FiscalYear, 1)
        source.status = "OPEN"
        source.closed_at = None
        source.reopened_at = datetime(2026, 1, 2)
        source.reopening_reason = "Correction test"
    book(client, "512000", "706000", "0.01")
    value = continuity(client)
    assert value["source_closed"] is False and value["source_unchanged"] is False
    assert value["balances_match"] is False and value["status"] == "PROVISIONAL"
    assert {row["account_number"] for row in value["differences"]} == {"512000", "120000"}
    assert generate(client, data).json()["detail"]["code"] == "OPENING_PREVIEW_CHANGED"


def test_database_rejects_duplicate_opening_and_unsafe_downgrade(client, database, settings):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from alembic import command
    from tests.conftest import migration_config

    book(client, "512000", "706000", "10.00")
    next_year(client)
    close(database)
    assert generate(client, request(client)).status_code == 200
    data = payload()
    data.update(fiscal_year_id=2, accounting_date="2026-01-01")
    manual = draft(client, data)
    with pytest.raises(IntegrityError), database.engine.begin() as connection:
        connection.execute(
            text("UPDATE accounting_entry SET source_type='OPENING' WHERE id=:id"),
            {"id": manual["id"]},
        )
    with pytest.raises(RuntimeError, match="Refusing to remove opening uniqueness"):
        command.downgrade(migration_config(settings), "0004_assets")
    assert continuity(client)["balances_match"] is True


def test_opening_migration_round_trip_preserves_existing_ledger(client, database, settings):
    from alembic import command
    from tests.conftest import migration_config

    book(client, "512000", "706000", "10.00")
    before = report(client)
    command.downgrade(migration_config(settings), "0004_assets")
    command.upgrade(migration_config(settings), "head")
    command.check(migration_config(settings))
    assert report(client) == before
