"""Batch depreciation posting: per-item status, idempotency, partial failure."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.integration.test_statements import book


@pytest.fixture
def client(settings, database):
    del database
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as api:
        assert (
            api.post(
                "/api/ledger/activity",
                json={"activity_name": "Actifs fictifs", "activity_start_date": "2025-01-01"},
            ).status_code
            == 201
        )
        assert api.post("/api/ledger/years", json=_year(2025)).status_code == 201
        assert (
            api.post(
                "/api/operations/properties",
                json={
                    "name": "Bien fictif",
                    "address": "Adresse fictive",
                    "acquisition_date": "2025-01-01",
                    "acquisition_price": "100000.00",
                    "land_value": "20000.00",
                    "building_value": "80000.00",
                },
            ).status_code
            == 201
        )
        yield api


def _year(year: int) -> dict[str, object]:
    return {
        "year": year,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "fiscal_vintage": str(year),
    }


def _furniture(label: str) -> dict[str, object]:
    return {
        "property_id": 1,
        "category": "FURNITURE",
        "label": label,
        "acquisition_date": "2025-07-01",
        "service_start_date": "2025-07-01",
        "acquisition_value": "1200.00",
        "depreciable_value": "1200.00",
        "non_depreciable_value": "0.00",
        "residual_value": "0.00",
        "method": "LINEAR",
        "useful_life_months": 60,
        "asset_account": "218400",
        "depreciation_account": "281840",
        "basis_reason": "Facture fictive MOB-001",
        "duration_reason": "Durée d’utilisation estimée à cinq ans",
    }


def _item(period_id: int, piece: str | None = None) -> dict[str, object]:
    return {
        "period_id": period_id,
        "request_id": f"dotation-{period_id}-poste",
        "piece_reference": piece or f"DOT-{period_id}",
    }


def _post(client: TestClient, items: list[dict[str, object]], key: str, year_id: int = 1):
    return client.post(
        f"/api/assets/years/{year_id}/post",
        json={"items": items},
        headers={"Idempotency-Key": key},
    )


def _entry_count(client: TestClient) -> int:
    response = client.get("/api/ledger/entries?fiscal_year_id=1")
    assert response.status_code == 200, response.text
    count = response.json()["count"]
    assert isinstance(count, int)
    return count


def test_batch_requires_an_idempotency_key_and_unique_periods(client):
    missing = client.post(
        "/api/assets/years/1/post",
        json={"items": [_item(1)]},
    )
    assert missing.status_code == 422
    assert missing.json()["detail"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    duplicate = _post(client, [_item(1), _item(1)], "batch-duplicate")
    assert duplicate.status_code == 422
    assert duplicate.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_lost_response_retry_does_not_double_post(client):
    assert client.post("/api/assets", json=_furniture("Mobilier fictif")).status_code == 201
    book(client, "218400", "108000", "1200.00")
    periods = client.post("/api/assets/years/1/calculate").json()
    assert len(periods) == 1
    items = [_item(periods[0]["id"], "DOT-PERDU")]
    first = _post(client, items, "batch-reponse-perdue")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["replayed"] is False
    assert body["posted_count"] == 1
    assert body["items"][0]["status"] == "posted"
    entry_id = body["items"][0]["entry_id"]
    # The client never saw `first`. The same key must return that entry, not a second one.
    second = _post(client, items, "batch-reponse-perdue")
    assert second.status_code == 200, second.text
    replay = second.json()
    assert replay["replayed"] is True
    assert replay["items"][0]["entry_id"] == entry_id
    assert _entry_count(client) == 2
    entry = client.get(f"/api/ledger/entries/{entry_id}").json()
    assert entry["status"] == "VALIDATED"
    assert entry["piece_reference"] == "DOT-PERDU"
    assert entry["total_debit"] == periods[0]["amount"]
    conflict = _post(client, [_item(periods[0]["id"], "DOT-AUTRE")], "batch-reponse-perdue")
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert client.get(f"/api/ledger/entries/{entry_id}").json()["piece_reference"] == "DOT-PERDU"
    assert _entry_count(client) == 2


def test_natural_key_replays_an_already_posted_period(client):
    assert client.post("/api/assets", json=_furniture("Mobilier fictif")).status_code == 201
    book(client, "218400", "108000", "1200.00")
    period = client.post("/api/assets/years/1/calculate").json()[0]
    posted = client.post(
        f"/api/assets/periods/{period['id']}/post",
        json={"request_id": "dotation-unique-01", "piece_reference": "DOT-UNIT"},
    )
    assert posted.status_code == 201, posted.text
    batch = _post(client, [_item(period["id"], "DOT-AUTRE-PIECE")], "batch-cle-naturelle")
    assert batch.status_code == 200, batch.text
    item = batch.json()["items"][0]
    assert item["status"] == "posted"
    assert item["replayed"] is True
    assert item["entry_id"] == posted.json()["id"]
    stored = client.get(f"/api/ledger/entries/{item['entry_id']}").json()
    assert stored["piece_reference"] == "DOT-UNIT"
    assert _entry_count(client) == 2


def test_error_in_the_middle_keeps_earlier_items_and_skips_the_rest(client):
    assert client.post("/api/assets", json=_furniture("Premier meuble")).status_code == 201
    assert client.post("/api/assets", json=_furniture("Second meuble")).status_code == 201
    book(client, "218400", "108000", "2400.00")
    assert client.post("/api/ledger/years", json=_year(2026)).status_code == 201
    first_year = client.post("/api/assets/years/1/calculate").json()
    second_year = client.post("/api/assets/years/2/calculate").json()
    assert len(first_year) == 2
    assert len(second_year) == 2
    foreign_id = second_year[0]["id"]
    items = [_item(first_year[0]["id"]), _item(foreign_id), _item(first_year[1]["id"])]
    response = _post(client, items, "batch-milieu")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["status"] for item in body["items"]] == ["posted", "error", "skipped"]
    assert body["items"][1]["code"] == "PERIOD_YEAR_MISMATCH"
    assert body["items"][2]["code"] == "BATCH_INTERRUPTED"
    assert body["posted_count"] == 1
    assert body["failed_count"] == 1
    assert body["skipped_count"] == 1
    assert _entry_count(client) == 2
    listed = client.get("/api/assets/years/1/periods").json()
    by_id = {row["id"]: row["status"] for row in listed}
    assert by_id[first_year[0]["id"]] == "POSTED"
    assert by_id[first_year[1]["id"]] == "CALCULATED"
    # A lost response of this partial lot must not continue into the skipped period.
    replay = _post(client, items, "batch-milieu")
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True
    assert replay.json()["items"] == body["items"]
    listed = client.get("/api/assets/years/1/periods").json()
    replayed = {row["id"]: row["status"] for row in listed}
    assert replayed[first_year[1]["id"]] == "CALCULATED"
    assert _entry_count(client) == 2
    # A new key posts only what is still open.
    follow = _post(client, [_item(first_year[1]["id"])], "batch-suite")
    assert follow.status_code == 200, follow.text
    assert follow.json()["posted_count"] == 1
    assert follow.json()["items"][0]["replayed"] is False
    assert _entry_count(client) == 3


def test_concurrent_same_key_posts_once(client):
    assert client.post("/api/assets", json=_furniture("Mobilier fictif")).status_code == 201
    book(client, "218400", "108000", "1200.00")
    period = client.post("/api/assets/years/1/calculate").json()[0]
    items = [_item(period["id"])]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: _post(client, items, "batch-double-clic"), range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    bodies = [response.json() for response in responses]
    assert {body["items"][0]["entry_id"] for body in bodies} == {bodies[0]["items"][0]["entry_id"]}
    assert _entry_count(client) == 2
    assert sorted(body["replayed"] for body in bodies) == [False, True]
