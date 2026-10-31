from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import AccountingEntry, AccountingEntryLine, LedgerEvent
from app.services import result_closing
from app.services.ledger import fail
from tests.integration.test_ledger import client as seeded_client  # noqa: F401
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


@pytest.fixture
def bare_client(seeded_client):  # noqa: F811
    return seeded_client


def counts(database):
    with database.engine.connect() as connection:
        return tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in (AccountingEntry, AccountingEntryLine, LedgerEvent)
        )


def centralize(client, result, account="120000", request_id=None, create_accounts=None):
    body = {
        "request_id": request_id or str(uuid4()),
        "journal_code": "OD",
        "piece_reference": "CENT-1",
        "justification": "Centralisation confirmée après contrôle du résultat.",
        "result_account": account,
        "expected_result": result,
    }
    if create_accounts is not None:
        body["create_accounts"] = create_accounts
    return client.post("/api/ledger/years/1/centralization", json=body)


BENEFIT = {
    "number": "120000",
    "label": "Résultat de l’exercice (bénéfice)",
    "account_type": "EQUITY",
}
DEFICIT = {
    "number": "129000",
    "label": "Résultat de l’exercice (déficit)",
    "account_type": "EQUITY",
}


def chart_snapshot(client, database):
    rows = client.get("/api/ledger/accounts").json()
    with database.engine.connect() as connection:
        events = connection.scalar(select(func.count()).select_from(LedgerEvent))
    chart = [(row["number"], row["label"], row["active"]) for row in rows]
    return chart, events


def appropriate(client, amount, source="120000", target="108000", request_id=None):
    return client.post(
        "/api/ledger/years/1/appropriation",
        json={
            "request_id": request_id or str(uuid4()),
            "journal_code": "OD",
            "piece_reference": "AFF-1",
            "justification": "Affectation confirmée vers le compte de l’exploitant.",
            "source_account": source,
            "target_account": target,
            "expected_amount": amount,
        },
    )


def test_profit_rubrics_centralization_and_appropriation(client):
    book(client, "512000", "108000", "2000.00")
    book(client, "411000", "706000", "900.25")
    book(client, "615000", "401000", "100.15")
    book(client, "661000", "512000", "0.10")
    result = report(client)
    cash = next(
        row for row in result["presentation"]["balance_rubrics"] if row["code"] == "TRESORERIE"
    )
    assert cash["total"] == "1999.90"
    natures = {row["code"]: row["total"] for row in result["presentation"]["income_rubrics"]}
    assert natures["PRODUITS_EXPLOITATION"] == "900.25"
    assert natures["SERVICES_EXTERIEURS"] == "100.15"
    assert natures["CHARGES_FINANCIERES"] == "0.10"
    assert result["presentation"]["reclassifications_applied"] is False
    preview = client.get("/api/ledger/years/1/centralization-preview").json()
    assert preview["result"] == "800.00"
    assert preview["read_only"] is True
    assert preview["proposed_accounts"] == []
    posted = centralize(client, "800.00")
    assert posted.status_code == 200, posted.text
    assert posted.json()["created"] is True
    after = report(client)
    assert (
        after["income_statement"]["result"] == after["balance_sheet"]["current_result"] == "800.00"
    )
    assert after["income_statement"]["total_income"] == "900.25"
    equity = {row["account_number"]: row["amount"] for row in after["balance_sheet"]["equity"]}
    assert "120000" not in equity
    assert equity["108000"] == "2000.00"
    natures = {row["code"]: row["total"] for row in after["presentation"]["income_rubrics"]}
    assert natures["PRODUITS_EXPLOITATION"] == "900.25"
    capitals = next(
        row for row in after["presentation"]["balance_rubrics"] if row["code"] == "CAPITAUX"
    )
    assert capitals["total"] == "2000.00"
    assert all(row["account_number"] != "120000" for row in capitals["accounts"])
    proposal = client.get("/api/ledger/years/1/appropriation-preview").json()["proposals"][0]
    assert proposal["amount"] == "800.00"
    affected = appropriate(client, "800.00")
    assert affected.status_code == 200, affected.text
    final = report(client)
    equity = {row["account_number"]: row["amount"] for row in final["balance_sheet"]["equity"]}
    assert equity["108000"] == "2800.00"
    assert "120000" not in equity
    assert final["income_statement"]["result"] == "800.00"
    assert final["balance_sheet"]["current_result"] == "0.00"
    assert final["balance_sheet"]["balanced"] is True


def test_loss_uses_129_and_cent_amounts(client):
    book(client, "615000", "401000", "10.01")
    assert (
        client.get("/api/ledger/years/1/centralization-preview").json()["proposed_accounts"] == []
    )
    assert (
        centralize(client, "-10.01", "120000").json()["detail"]["code"] == "INVALID_RESULT_ACCOUNT"
    )
    posted = centralize(client, "-10.01", "129000")
    assert posted.status_code == 200, posted.text
    body = report(client)
    assert body["income_statement"]["result"] == body["balance_sheet"]["current_result"] == "-10.01"
    assert all(row["account_number"] != "129000" for row in body["balance_sheet"]["equity"])
    affected = appropriate(client, "10.01", "129000", "108000")
    assert affected.status_code == 200, affected.text
    equity = {
        row["account_number"]: row["amount"] for row in report(client)["balance_sheet"]["equity"]
    }
    assert equity["108000"] == "-10.01"


def test_idempotent_retry_conflict_and_locked_year(client, database):
    from datetime import datetime

    from app.models import FiscalYear

    book(client, "512000", "706000", "50.00")
    request_id = str(uuid4())
    first = centralize(client, "50.00", request_id=request_id).json()
    before = counts(database)
    replay = centralize(client, "50.00", request_id=request_id).json()
    assert replay["created"] is False
    assert replay["entry"] == first["entry"]
    body = {
        "request_id": request_id,
        "journal_code": "OD",
        "piece_reference": "AUTRE",
        "justification": "Centralisation confirmée après contrôle du résultat.",
        "result_account": "120000",
        "expected_result": "50.00",
    }
    conflict = client.post("/api/ledger/years/1/centralization", json=body)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "RESULT_REQUEST_CONFLICT"
    other = centralize(client, "50.00")
    assert other.status_code == 409
    assert other.json()["detail"]["code"] == "CENTRALIZATION_EXISTS"
    assert counts(database) == before
    with database.sessions.begin() as session:
        year = session.get(FiscalYear, 1)
        assert year is not None
        year.status = "CLOSED"
        year.closed_at = datetime(2026, 1, 1)
    refused = centralize(client, "50.00")
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "YEAR_LOCKED"


def test_rollback_on_audit_failure_and_concurrency(client, database, monkeypatch):
    book(client, "512000", "706000", "20.00")

    def reject_audit(*args, **kwargs):
        fail("TEST_AUDIT_FAILURE", "Échec simulé après validation.")

    before = counts(database)
    with monkeypatch.context() as patch:
        patch.setattr(result_closing, "event", reject_audit)
        response = centralize(client, "20.00")
    assert response.status_code == 409
    assert counts(database) == before
    data_id = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: centralize(client, "20.00", request_id=data_id), range(2))
        )
    assert [item.status_code for item in responses] == [200, 200]
    assert responses[0].json()["entry"]["id"] == responses[1].json()["entry"]["id"]
    assert counts(database)[0] == before[0] + 1


def test_stale_result_drafts_and_overdraft_warning(client):
    book(client, "615000", "512000", "15.00")
    draft = client.post(
        "/api/ledger/entries",
        json={
            "fiscal_year_id": 1,
            "journal_code": "OD",
            "accounting_date": "2025-03-01",
            "piece_reference": "BROUILLON",
            "piece_date": "2025-03-01",
            "label": "Brouillon exclu",
            "lines": [
                {"account_number": "615000", "label": "Charge", "debit": "1.00", "credit": "0.00"},
                {"account_number": "401000", "label": "Dette", "debit": "0.00", "credit": "1.00"},
            ],
        },
    )
    assert draft.status_code == 201
    blocked = centralize(client, "-15.00", "129000")
    assert blocked.json()["detail"]["code"] == "YEAR_DRAFTS"
    warnings = report(client)["presentation"]["warnings"]
    assert any(
        item["code"] == "DECOUVERT" and item["account_number"] == "512000" for item in warnings
    )
    assert report(client)["presentation"]["balance_rubrics"]
    treso = next(
        r for r in report(client)["presentation"]["balance_rubrics"] if r["code"] == "TRESORERIE"
    )
    assert treso["accounts"][0]["account_number"] == "512000"


def test_zero_result_nets_classes_without_result_account(client):
    book(client, "512000", "706000", "40.00")
    book(client, "615000", "512000", "40.00")
    preview = client.get("/api/ledger/years/1/centralization-preview").json()
    assert preview["proposed_accounts"] == []
    refused = centralize(client, "0.00", "120000")
    assert refused.json()["detail"]["code"] == "UNEXPECTED_RESULT_ACCOUNT"
    posted = centralize(client, "0.00", None)
    assert posted.status_code == 200, posted.text
    assert report(client)["income_statement"]["result"] == "0.00"
    assert client.get("/api/ledger/years/1/appropriation-preview").json()["proposals"] == []


def test_preview_does_not_change_chart_and_confirmation_creates_account(bare_client, database):
    book(bare_client, "512000", "706000", "50.00")
    before = chart_snapshot(bare_client, database)
    preview = bare_client.get("/api/ledger/years/1/centralization-preview")
    assert preview.status_code == 200, preview.text
    assert preview.json()["proposed_accounts"] == [BENEFIT]
    assert chart_snapshot(bare_client, database) == before
    missing = centralize(bare_client, "50.00")
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "INVALID_RESULT_ACCOUNT"
    wrong = centralize(bare_client, "50.00", "129000", create_accounts=[DEFICIT])
    assert wrong.status_code == 409
    assert wrong.json()["detail"]["code"] == "UNEXPECTED_ACCOUNT_CREATION"
    mismatched = centralize(
        bare_client,
        "50.00",
        create_accounts=[{**BENEFIT, "label": "Autre libellé"}],
    )
    assert mismatched.status_code == 409
    assert mismatched.json()["detail"]["code"] == "UNEXPECTED_ACCOUNT_CREATION"
    assert chart_snapshot(bare_client, database) == before
    request_id = str(uuid4())
    posted = centralize(bare_client, "50.00", request_id=request_id, create_accounts=[BENEFIT])
    assert posted.status_code == 200, posted.text
    assert posted.json()["created"] is True
    numbers = [row["number"] for row in bare_client.get("/api/ledger/accounts").json()]
    assert numbers.count("120000") == 1
    assert "129000" not in numbers
    body = report(bare_client)
    assert body["income_statement"]["result"] == body["balance_sheet"]["current_result"] == "50.00"
    assert all(row["account_number"] != "120000" for row in body["balance_sheet"]["equity"])
    replay = centralize(bare_client, "50.00", request_id=request_id, create_accounts=[BENEFIT])
    assert replay.status_code == 200, replay.text
    assert replay.json()["created"] is False
    assert replay.json()["entry"]["id"] == posted.json()["entry"]["id"]
    conflict = centralize(bare_client, "50.00", request_id=request_id, create_accounts=[])
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "RESULT_REQUEST_CONFLICT"
    again = centralize(bare_client, "50.00", create_accounts=[BENEFIT])
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "CENTRALIZATION_EXISTS"
    assert numbers == [row["number"] for row in bare_client.get("/api/ledger/accounts").json()]


def test_loss_preview_proposes_only_deficit_account(bare_client, database):
    book(bare_client, "615000", "401000", "10.01")
    before = chart_snapshot(bare_client, database)
    preview = bare_client.get("/api/ledger/years/1/centralization-preview").json()
    assert preview["proposed_accounts"] == [DEFICIT]
    assert chart_snapshot(bare_client, database) == before
    posted = centralize(bare_client, "-10.01", "129000", create_accounts=[DEFICIT])
    assert posted.status_code == 200, posted.text
    numbers = {row["number"] for row in bare_client.get("/api/ledger/accounts").json()}
    assert "129000" in numbers
    assert "120000" not in numbers


def test_zero_result_proposes_no_account_creation(bare_client, database):
    book(bare_client, "512000", "706000", "40.00")
    book(bare_client, "615000", "512000", "40.00")
    before = chart_snapshot(bare_client, database)
    preview = bare_client.get("/api/ledger/years/1/centralization-preview").json()
    assert preview["result"] == "0.00"
    assert preview["proposed_accounts"] == []
    assert chart_snapshot(bare_client, database) == before
    posted = centralize(bare_client, "0.00", None)
    assert posted.status_code == 200, posted.text
    chart, _events = chart_snapshot(bare_client, database)
    assert chart == before[0]


def test_rejected_centralization_does_not_create_accounts(bare_client, database):
    book(bare_client, "512000", "706000", "50.00")
    before = chart_snapshot(bare_client, database)
    stale = centralize(bare_client, "1.00", create_accounts=[BENEFIT])
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "RESULT_CHANGED"
    assert chart_snapshot(bare_client, database) == before
    draft = bare_client.post(
        "/api/ledger/entries",
        json={
            "fiscal_year_id": 1,
            "journal_code": "OD",
            "accounting_date": "2025-03-01",
            "piece_reference": "BROUILLON",
            "piece_date": "2025-03-01",
            "label": "Brouillon exclu",
            "lines": [
                {"account_number": "615000", "label": "Charge", "debit": "1.00", "credit": "0.00"},
                {"account_number": "401000", "label": "Dette", "debit": "0.00", "credit": "1.00"},
            ],
        },
    )
    assert draft.status_code == 201, draft.text
    before = chart_snapshot(bare_client, database)
    blocked = centralize(bare_client, "50.00", create_accounts=[BENEFIT])
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "YEAR_DRAFTS"
    assert chart_snapshot(bare_client, database) == before


def test_existing_prefix_account_is_not_replaced_by_canonical(bare_client, database):
    created = bare_client.post(
        "/api/ledger/accounts",
        json={"number": "120100", "label": "Résultat à affecter", "account_type": "EQUITY"},
    )
    assert created.status_code == 201, created.text
    book(bare_client, "512000", "706000", "50.00")
    before = chart_snapshot(bare_client, database)
    preview = bare_client.get("/api/ledger/years/1/centralization-preview").json()
    assert preview["proposed_accounts"] == []
    assert chart_snapshot(bare_client, database) == before
    posted = centralize(bare_client, "50.00", "120100")
    assert posted.status_code == 200, posted.text
    numbers = {row["number"] for row in bare_client.get("/api/ledger/accounts").json()}
    assert "120100" in numbers
    assert "120000" not in numbers


def test_inactive_canonical_account_is_not_recreated(bare_client, database):
    created = bare_client.post("/api/ledger/accounts", json=BENEFIT)
    assert created.status_code == 201, created.text
    changed = bare_client.patch("/api/ledger/accounts/120000/active", json={"active": False})
    assert changed.status_code == 200, changed.text
    book(bare_client, "512000", "706000", "50.00")
    before = chart_snapshot(bare_client, database)
    preview = bare_client.get("/api/ledger/years/1/centralization-preview").json()
    assert preview["proposed_accounts"] == []
    assert chart_snapshot(bare_client, database) == before
    refused = centralize(bare_client, "50.00", create_accounts=[BENEFIT])
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "UNEXPECTED_ACCOUNT_CREATION"
    direct = centralize(bare_client, "50.00")
    assert direct.status_code == 409
    assert direct.json()["detail"]["code"] == "INVALID_RESULT_ACCOUNT"
    assert chart_snapshot(bare_client, database) == before


def test_account_creation_rolls_back_with_failed_centralization(bare_client, database, monkeypatch):
    book(bare_client, "512000", "706000", "20.00")
    before = chart_snapshot(bare_client, database)

    def reject(*args, **kwargs):
        fail("TEST_POST_FAILURE", "Échec simulé après création du compte.")

    with monkeypatch.context() as patch:
        patch.setattr(result_closing, "post_entry", reject)
        response = centralize(bare_client, "20.00", create_accounts=[BENEFIT])
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TEST_POST_FAILURE"
    assert chart_snapshot(bare_client, database) == before


RESULT = "78.49"


def _credit(client, number: str) -> str:
    rows = client.get("/api/ledger/years/1/balance").json()["balance"]
    row = next((item for item in rows if item["account_number"] == number), None)
    if row is None:
        return "0.00"
    return str(row["credit_balance"])


def _tax_forms(client) -> tuple[str, str]:
    fiscal = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    sheet = client.get("/api/filing/years/1/efi").json()
    benefit = next(
        field["value"]
        for field in sheet["liasse"]["fields"]
        if field["form_ref"] == "2033-B-SD" and field["official_case"] == "312"
    )
    box_5na = next(
        line["amount"] for line in sheet["personal_return"]["lines"] if line["case"] == "5NA"
    )
    return str(benefit), str(box_5na)


def test_statements_120_2033b_and_5na_stay_aligned(client):
    """The same file shows one result before centralization, and still after it.

    Account 120 is zero until the result is centralised. Afterwards it carries
    that result, and the statements no longer list it under other equity.
    """
    identity = client.post("/api/ledger/activity/identity", json={"siren": "123456789"})
    assert identity.status_code == 200, identity.text
    book(client, "512000", "706000", "100.00")
    book(client, "615000", "401000", "21.51")

    before = report(client)
    benefit, box_5na = _tax_forms(client)
    assert before["status"] == "PROVISIONAL"
    assert before["income_statement"]["result"] == RESULT
    assert before["balance_sheet"]["current_result"] == RESULT
    assert benefit == RESULT
    assert box_5na == RESULT
    assert _credit(client, "120000") == "0.00"
    equity_numbers = {row["account_number"] for row in before["balance_sheet"]["equity"]}
    assert "120000" not in equity_numbers
    assert "129000" not in equity_numbers
    assert before["balance_sheet"]["balanced"] is True

    posted = centralize(client, RESULT)
    assert posted.status_code == 200, posted.text
    after = report(client)
    benefit, box_5na = _tax_forms(client)
    assert after["income_statement"]["result"] == RESULT
    assert after["balance_sheet"]["current_result"] == RESULT
    assert after["income_statement"]["total_income"] == "100.00"
    assert after["income_statement"]["total_expenses"] == "21.51"
    assert {row["account_number"] for row in after["income_statement"]["income"]} == {"706000"}
    assert {row["account_number"] for row in after["income_statement"]["expenses"]} == {"615000"}
    assert _credit(client, "120000") == RESULT
    assert benefit == RESULT
    assert box_5na == RESULT
    equity_numbers = {row["account_number"] for row in after["balance_sheet"]["equity"]}
    assert "120000" not in equity_numbers
    assert "129000" not in equity_numbers
    assert (
        after["balance_sheet"]["total_assets"]
        == after["balance_sheet"]["total_liabilities_and_equity"]
    )
    assert after["balance_sheet"]["balanced"] is True
    assert after["status"] == "PROVISIONAL"

    precheck = client.get("/api/filing/years/1/precheck")
    assert precheck.status_code == 200, precheck.text
    assert precheck.json()["blocking"] is False, precheck.text
    codes = [item["code"] for item in precheck.json()["warnings"]]
    ready = client.post("/api/filing/years/1/ready", json={"acknowledged": codes})
    assert ready.status_code == 200, ready.text
    closed = client.post("/api/filing/years/1/close", json={"confirmation": "CLOTURER"})
    assert closed.status_code == 200, closed.text
    final = report(client)
    assert final["status"] == "CLOSED"
    assert final["presentation"]["status"] == "CLOSED"
    assert final["income_statement"]["result"] == RESULT
    assert final["balance_sheet"]["current_result"] == RESULT
    assert _credit(client, "120000") == RESULT


def test_reversing_centralization_restores_the_open_result(client):
    book(client, "512000", "706000", "40.00")
    posted = centralize(client, "40.00")
    assert posted.status_code == 200, posted.text
    reversal = client.post(
        f"/api/ledger/entries/{posted.json()['entry']['id']}/reverse",
        json={
            "accounting_date": "2025-12-31",
            "piece_reference": "EXT-CENT",
            "reason": "Extourne de la centralisation de test.",
        },
    )
    assert reversal.status_code == 201, reversal.text
    body = report(client)
    assert body["income_statement"]["result"] == "40.00"
    assert body["balance_sheet"]["current_result"] == "40.00"
    assert _credit(client, "120000") == "0.00"
    preview = client.get("/api/ledger/years/1/centralization-preview").json()
    assert preview["result"] == "40.00"
    assert preview["recentralization_required"] is False
