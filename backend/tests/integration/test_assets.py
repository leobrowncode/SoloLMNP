from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.main import create_app


@pytest.fixture
def client(settings, database):
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as client:
        assert (
            client.post(
                "/api/ledger/activity",
                json={"activity_name": "Actifs fictifs", "activity_start_date": "2025-01-01"},
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/ledger/years",
                json={
                    "year": 2025,
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                    "fiscal_vintage": "2025",
                },
            ).status_code
            == 201
        )
        assert (
            client.post(
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
        yield client


def furniture(**changes):
    return {
        "property_id": 1,
        "category": "FURNITURE",
        "label": "Mobilier fictif",
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
        **changes,
    }


def building(**changes):
    return furniture(
        category="BUILDING",
        label="Construction fictive",
        acquisition_date="2025-01-01",
        service_start_date="2025-01-01",
        acquisition_value="80000.00",
        depreciable_value="80000.00",
        useful_life_months=360,
        asset_account="213000",
        depreciation_account="281300",
        basis_reason="Ventilation documentée du prix d’acquisition",
        duration_reason="Durée d’utilisation estimée à trente ans",
        **changes,
    )


def component(value="40000.00", **changes):
    return {
        "category": "STRUCTURE",
        "label": "Composant fictif",
        "value": value,
        "useful_life_months": 360,
        "service_start_date": "2025-01-01",
        "asset_account": "213000",
        "depreciation_account": "281300",
        "basis_reason": "Ventilation technique fictive",
        "duration_reason": "Durée documentée du composant fictif",
        **changes,
    }


def test_land_can_never_be_depreciated(client, database):
    invalid = furniture(category="LAND", asset_account="211000")
    response = client.post("/api/assets", json=invalid)
    assert response.status_code == 422
    valid = furniture(
        category="LAND",
        label="Terrain fictif",
        acquisition_value="20000.00",
        depreciable_value="0.00",
        non_depreciable_value="20000.00",
        method="NONE",
        useful_life_months=None,
        asset_account="211000",
        depreciation_account=None,
        duration_reason="",
    )
    assert client.post("/api/assets", json=valid).status_code == 201
    assert client.post("/api/assets/years/1/calculate").json() == []
    with pytest.raises(IntegrityError), database.sessions.begin() as session:
        session.execute(text("UPDATE asset SET depreciable_value=1 WHERE id=1"))


def test_midyear_furniture_actual_day_schedule_and_posting(client):
    assert client.post("/api/assets", json=furniture()).status_code == 201
    periods = client.post("/api/assets/years/1/calculate").json()
    assert len(periods) == 1
    row = periods[0]
    total_days = (date(2030, 6, 30) - date(2025, 7, 1)).days + 1
    expected = int(
        (Decimal(120000) * Decimal(184) / Decimal(total_days)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    assert row["amount"] == f"{expected // 100}.{expected % 100:02d}"
    assert row["days"] == 184
    assert client.post("/api/assets/years/1/calculate").json() == periods
    posted = client.post(
        f"/api/assets/periods/{row['id']}/post",
        json={"request_id": "depreciation-2025-001", "piece_reference": "DOT-2025-001"},
    )
    assert posted.status_code == 201, posted.text
    entry = posted.json()
    assert entry["source_type"] == "DEPRECIATION"
    assert entry["total_debit"] == row["amount"]
    assert {line["account_number"] for line in entry["lines"]} == {"681100", "281840"}
    assert (
        client.post(
            f"/api/ledger/entries/{entry['id']}/reverse",
            json={
                "accounting_date": "2025-12-31",
                "piece_reference": "EXT-DOT-001",
                "reason": "Correction de test",
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/assets/periods/{row['id']}/post",
            json={"request_id": "depreciation-2025-001", "piece_reference": "DOT-2025-001"},
        ).json()
        == entry
    )


def test_components_must_exactly_cover_building_base(client):
    assert client.post("/api/assets", json=building()).status_code == 201
    assert client.post("/api/assets/1/components", json=component()).status_code == 201
    incomplete = client.post("/api/assets/years/1/calculate")
    assert incomplete.status_code == 422
    assert incomplete.json()["detail"]["code"] == "DECOMPOSITION_INCOMPLETE"
    assert (
        client.post(
            "/api/assets/1/components", json=component(label="Second composant")
        ).status_code
        == 201
    )
    periods = client.post("/api/assets/years/1/calculate").json()
    assert len(periods) == 2
    assert all(row["target_type"] == "COMPONENT" for row in periods)
    assert (
        client.post(
            "/api/assets/1/components", json=component(value="1.00", label="Excédent")
        ).status_code
        == 422
    )


def test_cumulative_schedule_never_exceeds_base_and_finishes_exactly(client):
    assert (
        client.post(
            "/api/assets",
            json=furniture(
                acquisition_date="2025-01-01",
                service_start_date="2025-01-01",
                useful_life_months=24,
            ),
        ).status_code
        == 201
    )
    for year in (2026,):
        assert (
            client.post(
                "/api/ledger/years",
                json={
                    "year": year,
                    "start_date": f"{year}-01-01",
                    "end_date": f"{year}-12-31",
                    "fiscal_vintage": str(year),
                },
            ).status_code
            == 201
        )
    rows = []
    for year_id in (1, 2):
        rows.extend(client.post(f"/api/assets/years/{year_id}/calculate").json())
    assert sum(Decimal(row["amount"]) for row in rows) == Decimal("1200.00")
    assert rows[-1]["accumulated"] == "1200.00"
    assert rows[-1]["net_book_value"] == "0.00"
    assert all(Decimal(row["accumulated"]) <= Decimal(row["base"]) for row in rows)


def test_closed_year_and_invalid_accounts_are_rejected(client, database):
    assert (
        client.post("/api/assets", json=furniture(depreciation_account="512000")).status_code == 422
    )
    assert client.post("/api/assets", json=furniture()).status_code == 201
    with database.sessions.begin() as session:
        session.execute(
            text("UPDATE fiscal_year SET status='CLOSED', closed_at=CURRENT_TIMESTAMP WHERE id=1")
        )
    assert client.post("/api/assets/years/1/calculate").status_code == 409


def test_raw_sql_cannot_fabricate_posted_period(client, database):
    assert client.post("/api/assets", json=furniture()).status_code == 201
    row = client.post("/api/assets/years/1/calculate").json()[0]
    with pytest.raises(IntegrityError), database.sessions.begin() as session:
        session.execute(
            text(
                "INSERT INTO depreciation_period "
                "(schedule_id,fiscal_year_id,period_start,period_end,days,amount,"
                "accumulated,net_book_value,status,accounting_entry_id,created_at) "
                "VALUES (1,1,'2025-01-01','2025-01-02',2,1,1,1,'POSTED',NULL,CURRENT_TIMESTAMP)"
            )
        )
    assert client.get("/api/assets/years/1/periods").json() == [row]
