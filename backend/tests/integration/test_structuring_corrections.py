"""Controlled corrections keep an audit trail and invalidate dependent outputs."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.database import Database
from app.main import create_app
from app.models import (
    AuditEvent,
    DepreciationSchedule,
    FiscalComputation,
    FiscalYear,
    TaxReturnSnapshot,
)
from tests.integration.test_assets import _open_account, building, component, furniture, land
from tests.integration.test_statements import book


@pytest.fixture
def client(settings, database):
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as api:
        assert (
            api.post(
                "/api/ledger/activity",
                json={"activity_name": "Corrections fictives", "activity_start_date": "2025-01-01"},
            ).status_code
            == 201
        )
        assert (
            api.post(
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


def _audits(database: Database, entity: str | None = None) -> list[AuditEvent]:
    with database.sessions.begin() as session:
        query = select(AuditEvent).order_by(AuditEvent.id)
        if entity is not None:
            query = query.where(AuditEvent.entity == entity)
        return list(session.scalars(query))


def _code(response) -> str:
    return str(response.json()["detail"]["code"])


def test_furniture_duration_is_audited_before_any_period(client, database):
    assert client.post("/api/assets", json=furniture()).status_code == 201
    listed = client.get("/api/assets").json()
    assert listed[0]["correction"] == {"locks": [], "calculated_periods": 0}
    corrected = client.patch(
        "/api/assets/1",
        json={"useful_life_months": 84, "reason": "Durée d’usage revue à sept ans"},
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["useful_life_months"] == 84
    assert corrected.json()["invalidation"]["dropped_period_ids"] == []
    events = _audits(database, "asset")
    assert len(events) == 1
    assert events[0].action == "CORRECTED"
    assert events[0].reason == "Durée d’usage revue à sept ans"
    assert events[0].before["useful_life_months"] == 60
    assert events[0].after["useful_life_months"] == 84
    refused = client.patch(
        "/api/assets/1",
        json={
            "asset_account": "213000",
            "depreciation_account": "281300",
            "reason": "Mauvais couple",
        },
    )
    assert refused.status_code == 422
    assert _code(refused) == "ASSET_ACCOUNT_PAIR_INVALID"
    assert len(_audits(database, "asset")) == 1
    assert client.get("/api/assets").json()[0]["asset_account"] == "218400"


def test_custom_accounts_realign_an_existing_schedule(client, database):
    _open_account(client, "218410")
    _open_account(client, "281841")
    assert client.post("/api/assets", json=furniture()).status_code == 201
    assert len(client.post("/api/assets/years/1/calculate").json()) == 1
    corrected = client.patch(
        "/api/assets/1",
        json={
            "asset_account": "218410",
            "depreciation_account": "281841",
            "reason": "Sous-compte de mobilier ouvert",
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["invalidation"]["dropped_period_ids"]
    with database.sessions.begin() as session:
        schedule = session.scalar(
            select(DepreciationSchedule).where(DepreciationSchedule.asset_id == 1)
        )
        assert schedule is not None
        assert schedule.asset_account == "218410"
        assert schedule.depreciation_account == "281841"
        assert schedule.useful_life_months == 60
        assert schedule.end_date == date(2030, 6, 30)


def _shown_fiscal(client) -> dict[str, object]:
    response = client.get("/api/fiscal/years/1")
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def test_open_dependents_are_invalidated_with_the_plan(client, database):
    assert client.post("/api/assets", json=furniture()).status_code == 201
    assert client.post("/api/assets/years/1/calculate").status_code == 200
    assert client.post("/api/fiscal/years/1", json={"adjustments": []}).status_code == 200
    prior = _shown_fiscal(client)
    assert prior["invalidated"] is False
    assert prior["ledger_sha256"] == prior["current_ledger_sha256"]
    assert prior["structuring_sha256"] == prior["current_structuring_sha256"]
    with database.sessions.begin() as session:
        session.add(
            TaxReturnSnapshot(
                fiscal_year_id=1,
                generation=1,
                status="CURRENT",
                canonical_json="{}",
                sha256="a" * 64,
                ledger_sha256="b" * 64,
            )
        )
        year = session.get(FiscalYear, 1)
        assert year is not None
        year.status = "READY_TO_CLOSE"
    corrected = client.patch(
        "/api/assets/1",
        json={"useful_life_months": 84, "reason": "Durée revue avant clôture"},
    )
    assert corrected.status_code == 200, corrected.text
    body = corrected.json()
    assert body["invalidation"]["dropped_period_ids"]
    assert body["invalidation"]["fiscal_computations"] == 1
    assert body["invalidation"]["ready_years_reset"] == [1]
    assert body["invalidation"]["snapshots_superseded"] == 1
    assert client.get("/api/assets/years/1/periods").json() == []
    shown = _shown_fiscal(client)
    assert shown["id"] == prior["id"]
    assert shown["invalidated"] is True
    assert shown["fiscal_result"] == prior["fiscal_result"]
    assert shown["status"] == "research_only"
    assert shown["declarable"] is False
    assert shown["ledger_sha256"] == prior["ledger_sha256"]
    assert shown["structuring_sha256"] == prior["structuring_sha256"]
    assert shown["current_structuring_sha256"] != shown["structuring_sha256"]
    precheck = client.get("/api/filing/years/1/precheck")
    assert precheck.status_code == 200, precheck.text
    codes = [item["code"] for item in precheck.json()["errors"]]
    assert "FISCAL_NOT_COMPUTED" in codes
    liasse = client.get("/api/filing/years/1/package")
    assert liasse.status_code == 404
    assert liasse.json()["detail"]["code"] == "FISCAL_NOT_COMPUTED"
    with database.sessions.begin() as session:
        year = session.get(FiscalYear, 1)
        assert year is not None and year.status == "OPEN"
        schedule = session.scalar(
            select(DepreciationSchedule).where(DepreciationSchedule.asset_id == 1)
        )
        assert schedule is not None
        assert schedule.useful_life_months == 84
        assert schedule.end_date == date(2032, 6, 30)
        snap = session.scalar(select(TaxReturnSnapshot))
        assert snap is not None and snap.status == "SUPERSEDED"
    reset = [row for row in _audits(database) if row.action == "DEPENDENCIES_INVALIDATED"]
    assert reset[0].before == {"status": "READY_TO_CLOSE"}
    assert reset[0].after == {"status": "OPEN"}


def test_posted_dotation_freezes_plan_inputs_not_the_justification(client, database):
    assert client.post("/api/assets", json=furniture()).status_code == 201
    book(client, "218400", "108000", "1200.00")
    period = client.post("/api/assets/years/1/calculate").json()[0]
    posted = client.post(
        f"/api/assets/periods/{period['id']}/post",
        json={"request_id": "dotation-figee-01", "piece_reference": "DOT-FIGEE"},
    )
    assert posted.status_code == 201, posted.text
    assert client.post("/api/fiscal/years/1", json={"adjustments": []}).status_code == 200
    before = len(_audits(database, "asset"))
    refused = client.patch(
        "/api/assets/1",
        json={"useful_life_months": 84, "reason": "Durée après dotation"},
    )
    assert refused.status_code == 409
    assert _code(refused) == "DEPRECIATION_POSTED"
    assert len(_audits(database, "asset")) == before
    assert client.get("/api/assets").json()[0]["useful_life_months"] == 60
    clarified = client.patch(
        "/api/assets/1",
        json={
            "basis_reason": "Facture fictive MOB-001 précisée",
            "reason": "Précision du justificatif",
        },
    )
    assert clarified.status_code == 200, clarified.text
    assert clarified.json()["invalidation"]["fiscal_computations"] == 0
    assert client.get("/api/assets/years/1/periods").json()[0]["status"] == "POSTED"
    kept = _shown_fiscal(client)
    assert kept["invalidated"] is False
    assert kept["structuring_sha256"] == kept["current_structuring_sha256"]
    assert kept["ledger_sha256"] == kept["current_ledger_sha256"]
    with pytest.raises(IntegrityError) as caught, database.sessions.begin() as session:
        session.execute(text("UPDATE asset SET useful_life_months=84 WHERE id=1"))
    assert "ASSET_HAS_POSTED_DEPRECIATION" in str(caught.value)
    with database.sessions.begin() as session:
        session.execute(text("UPDATE asset SET basis_reason='Motif SQL conservé' WHERE id=1"))
        stored = session.scalar(text("SELECT basis_reason FROM asset WHERE id=1"))
        assert stored == "Motif SQL conservé"


def test_component_correction_touches_only_its_schedule(client, database):
    assert client.post("/api/assets", json=building()).status_code == 201
    assert (
        client.post("/api/assets/1/components", json=component(label="Gros œuvre")).status_code
        == 201
    )
    second = component(label="Toiture", asset_account="213500", depreciation_account="281350")
    assert client.post("/api/assets/1/components", json=second).status_code == 201
    periods = client.post("/api/assets/years/1/calculate").json()
    assert {row["target_label"] for row in periods} == {"Gros œuvre", "Toiture"}
    corrected = client.patch(
        "/api/assets/1/components/1",
        json={"useful_life_months": 240, "reason": "Durée du gros œuvre revue"},
    )
    assert corrected.status_code == 200, corrected.text
    remaining = client.get("/api/assets/years/1/periods").json()
    assert [row["target_label"] for row in remaining] == ["Toiture"]
    with database.sessions.begin() as session:
        first = session.scalar(
            select(DepreciationSchedule).where(DepreciationSchedule.component_id == 1)
        )
        other = session.scalar(
            select(DepreciationSchedule).where(DepreciationSchedule.component_id == 2)
        )
        assert first is not None and other is not None
        assert first.useful_life_months == 240
        assert other.useful_life_months == 360
    too_much = client.patch(
        "/api/assets/1/components/2",
        json={"value": "90000.00", "reason": "Valeur trop haute"},
    )
    assert too_much.status_code == 422
    assert _code(too_much) == "COMPONENT_TOTAL_MISMATCH"
    wrong_account = client.patch(
        "/api/assets/1/components/2",
        json={
            "asset_account": "218400",
            "depreciation_account": "281840",
            "reason": "Compte de mobilier refusé",
        },
    )
    assert wrong_account.status_code == 422
    assert _code(wrong_account) == "ASSET_ACCOUNT_PAIR_INVALID"
    early = client.patch(
        "/api/assets/1/components/2",
        json={"service_start_date": "2024-12-01", "reason": "Date trop ancienne"},
    )
    assert early.status_code == 422
    assert _code(early) == "COMPONENT_DATE_INVALID"


def test_component_value_cannot_exceed_the_base_before_a_plan(client):
    assert client.post("/api/assets", json=building()).status_code == 201
    assert client.post("/api/assets/1/components", json=component()).status_code == 201
    refused = client.patch(
        "/api/assets/1/components/1",
        json={"value": "90000.00", "reason": "Valeur au-dessus de la base"},
    )
    assert refused.status_code == 422
    assert _code(refused) == "COMPONENT_TOTAL_EXCEEDS_BASE"


def test_historical_pair_can_be_clarified_then_repaired(client, database):
    with database.sessions.begin() as session:
        session.execute(
            text(
                "INSERT INTO asset (property_id,category,label,acquisition_date,"
                "service_start_date,acquisition_value,depreciable_value,non_depreciable_value,"
                "residual_value,method,useful_life_months,asset_account,depreciation_account,"
                "basis_reason,duration_reason,notes,created_at) VALUES "
                "(1,'BUILDING','Construction incohérente','2025-01-01','2025-01-01',"
                "8000000,8000000,0,0,'LINEAR',360,'211000','281300',"
                "'Ancien couple conservé','Durée historique','',CURRENT_TIMESTAMP)"
            )
        )
    clarified = client.patch(
        "/api/assets/1",
        json={
            "basis_reason": "Ancien couple précisé sans réécriture",
            "reason": "Précision historique",
        },
    )
    assert clarified.status_code == 200, clarified.text
    assert clarified.json()["asset_account"] == "211000"
    assert "ne sont pas réécrits" in clarified.json()["account_warning"]
    repaired = client.patch(
        "/api/assets/1",
        json={
            "asset_account": "213000",
            "depreciation_account": "281300",
            "reason": "Couple ramené à la construction",
        },
    )
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["account_warning"] is None
    assert repaired.json()["asset_account"] == "213000"


def test_land_stays_non_depreciable_and_its_reason_can_change(client, database):
    assert client.post("/api/assets", json=land()).status_code == 201
    refused = client.patch(
        "/api/assets/1",
        json={"depreciable_value": "1.00", "reason": "Tentative d’amortir le terrain"},
    )
    assert refused.status_code == 422
    assert _code(refused) == "ASSET_CORRECTION_INVALID"
    clarified = client.patch(
        "/api/assets/1",
        json={"basis_reason": "Quote-part de terrain documentée", "reason": "Précision du terrain"},
    )
    assert clarified.status_code == 200, clarified.text
    with database.sessions.begin() as session:
        assert session.scalar(select(DepreciationSchedule.id)) is None


def test_booked_acquisition_freezes_value_and_leaves_duration_open(client):
    payload = furniture(acquisition_date="2025-01-01", service_start_date="2025-01-01")
    assert client.post("/api/assets", json=payload).status_code == 201
    entered = client.post(
        "/api/assets/properties/1/entry",
        json={"fiscal_year_id": 1, "piece_reference": "ENTREE-001", "confirm": True},
    )
    assert entered.status_code == 200, entered.text
    refused = client.patch(
        "/api/assets/1",
        json={
            "acquisition_value": "1500.00",
            "depreciable_value": "1500.00",
            "reason": "Valeur après entrée",
        },
    )
    assert refused.status_code == 409
    assert _code(refused) == "PROPERTY_ALREADY_BOOKED"
    assert entered.json()["entry_number"] in refused.json()["detail"]["message"]
    corrected = client.patch(
        "/api/assets/1",
        json={"useful_life_months": 72, "reason": "Durée revue avant dotation"},
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["useful_life_months"] == 72


def test_closed_fiscal_cap_blocks_life_not_the_service_date(client, database):
    assert client.post("/api/assets", json=furniture()).status_code == 201
    fiscal = client.post("/api/fiscal/years/1", json={"adjustments": []})
    assert fiscal.status_code == 200, fiscal.text
    labels = [row["label"] for row in fiscal.json()["details"]["depreciation_categories"]]
    assert "Mobilier fictif" in labels
    with database.engine.begin() as connection:
        connection.execute(
            text("UPDATE fiscal_year SET status='CLOSED', closed_at=CURRENT_TIMESTAMP WHERE id=1")
        )
    refused = client.patch(
        "/api/assets/1",
        json={"useful_life_months": 84, "reason": "Durée après clôture fiscale"},
    )
    assert refused.status_code == 409
    assert _code(refused) == "CLOSED_FISCAL_DEPENDENCY"
    assert client.get("/api/assets").json()[0]["useful_life_months"] == 60
    with database.sessions.begin() as session:
        computation = session.scalar(select(FiscalComputation))
        assert computation is not None and computation.invalidated_at is None
    clarified = client.patch(
        "/api/assets/1",
        json={
            "basis_reason": "Facture fictive MOB-001 précisée",
            "reason": "Précision après clôture",
        },
    )
    assert clarified.status_code == 200, clarified.text
    moved = client.patch(
        "/api/assets/1",
        json={"service_start_date": "2025-08-01", "reason": "Mise en service précisée"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["invalidation"]["fiscal_computations"] == 0
    assert moved.json()["service_start_date"] == "2025-08-01"


def test_loan_terms_stay_editable_after_a_movement(client, database):
    assert (
        client.post(
            "/api/operations/banks",
            json={"name": "Banque fictive", "account_number": "512000"},
        ).status_code
        == 201
    )
    created = client.post(
        "/api/operations/loans",
        json={
            "property_id": 1,
            "lender": "Banque fictive",
            "start_date": "2025-01-01",
            "initial_principal": "10000.00",
            "interest_rate": "3.50",
            "duration_months": 120,
            "principal_account": "164000",
        },
    )
    assert created.status_code == 201, created.text
    listed = client.get("/api/operations/loans").json()[0]
    assert listed["interest_rate"] == "3.50"
    assert listed["correction"]["locks"][0]["code"] == "LOAN_ACCOUNT_FIXED"
    funded = client.post(
        "/api/operations/loans/1/fund",
        json={
            "request_id": "fund-loan-0001",
            "fiscal_year_id": 1,
            "date": "2025-01-15",
            "piece_reference": "VIR-001",
            "amount": "10000.00",
            "bank_account_id": 1,
        },
    )
    assert funded.status_code == 201, funded.text
    refused = client.patch(
        "/api/operations/loans/1",
        json={"initial_principal": "9000.00", "reason": "Capital initial revu"},
    )
    assert refused.status_code == 409
    assert _code(refused) == "LOAN_REFERENCED"
    assert client.post("/api/fiscal/years/1", json={"adjustments": []}).status_code == 200
    renamed = client.patch(
        "/api/operations/loans/1",
        json={"lender": "Autre prêteur fictif", "reason": "Nom du prêteur corrigé"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["invalidation"]["fiscal_computations"] == 0
    renamed_fiscal = _shown_fiscal(client)
    assert renamed_fiscal["invalidated"] is False
    assert renamed_fiscal["structuring_sha256"] == renamed_fiscal["current_structuring_sha256"]
    rated = client.patch(
        "/api/operations/loans/1",
        json={"interest_rate": "2.50", "reason": "Taux contractuel corrigé"},
    )
    assert rated.status_code == 200, rated.text
    assert rated.json()["interest_rate_basis_points"] == 250
    assert rated.json()["invalidation"]["fiscal_computations"] == 1
    rated_fiscal = _shown_fiscal(client)
    assert rated_fiscal["invalidated"] is True
    assert rated_fiscal["fiscal_result"] == renamed_fiscal["fiscal_result"]
    assert rated_fiscal["current_structuring_sha256"] != rated_fiscal["structuring_sha256"]
    event = _audits(database, "loan")[-1]
    assert event.before["interest_rate_basis_points"] == 350
    assert event.after["interest_rate_basis_points"] == 250
    with pytest.raises(IntegrityError) as caught, database.sessions.begin() as session:
        session.execute(text("UPDATE loan SET initial_principal=1 WHERE id=1"))
    assert "LOAN_REFERENCED" in str(caught.value)
    with database.sessions.begin() as session:
        session.execute(text("UPDATE loan SET lender='Nom SQL' WHERE id=1"))


def test_property_financials_lock_when_an_asset_exists(client, database):
    assert client.post("/api/assets", json=furniture()).status_code == 201
    assert client.post("/api/fiscal/years/1", json={"adjustments": []}).status_code == 200
    refused = client.patch(
        "/api/operations/properties/1",
        json={"land_value": "10000.00", "reason": "Terrain administratif revu"},
    )
    assert refused.status_code == 409
    assert _code(refused) == "PROPERTY_HAS_ASSETS"
    renamed = client.patch(
        "/api/operations/properties/1",
        json={"name": "Bien renommé", "reason": "Nom du logement corrigé"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["invalidation"]["fiscal_computations"] == 0
    renamed_fiscal = _shown_fiscal(client)
    assert renamed_fiscal["invalidated"] is False
    assert renamed_fiscal["structuring_sha256"] == renamed_fiscal["current_structuring_sha256"]
    assert renamed_fiscal["ledger_sha256"] == renamed_fiscal["current_ledger_sha256"]
    with pytest.raises(IntegrityError) as caught, database.sessions.begin() as session:
        session.execute(text("UPDATE property SET land_value=1 WHERE id=1"))
    assert "PROPERTY_HAS_ASSETS" in str(caught.value)


def test_tenant_identity_locks_after_receipts_and_exit_stays_open(client):
    created = client.post(
        "/api/operations/properties/1/tenants",
        json={"name": "Locataire fictif", "monthly_rent": "800.00", "entry_date": "2025-01-01"},
    )
    assert created.status_code == 201, created.text
    updated = client.patch(
        "/api/operations/properties/1/tenants/1",
        json={"monthly_rent": "820.00", "reason": "Loyer convenu avant quittance"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["monthly_rent"] == "820.00"
    scheduled = client.post("/api/operations/properties/1/rents", json={"fiscal_year_id": 1})
    assert scheduled.status_code == 201, scheduled.text
    refused = client.patch(
        "/api/operations/properties/1/tenants/1",
        json={"monthly_rent": "900.00", "reason": "Loyer après quittances"},
    )
    assert refused.status_code == 409
    assert _code(refused) == "TENANT_HAS_RENTS"
    departure = client.patch(
        "/api/operations/properties/1/tenants/1",
        json={"exit_date": "2025-06-30", "reason": "Départ du locataire"},
    )
    assert departure.status_code == 200, departure.text
    assert departure.json()["exit_date"] == "2025-06-30"
    assert departure.json()["invalidation"]["fiscal_computations"] == 0


def test_bank_number_is_free_until_a_movement_exists(client):
    assert (
        client.post(
            "/api/operations/banks",
            json={"name": "Banque fictive", "account_number": "512000"},
        ).status_code
        == 201
    )
    _open_account(client, "512100")
    renamed = client.patch(
        "/api/operations/banks/1",
        json={"name": "Compte courant fictif", "reason": "Libellé de la banque"},
    )
    assert renamed.status_code == 200, renamed.text
    moved = client.patch(
        "/api/operations/banks/1",
        json={"account_number": "512100", "reason": "Compte 512 dédié"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["account_number"] == "512100"
    operation = client.post(
        "/api/operations",
        json={
            "request_id": "bank-lock-0001",
            "kind": "EXPENSE",
            "property_id": 1,
            "fiscal_year_id": 1,
            "date": "2025-02-01",
            "piece_date": "2025-02-01",
            "piece_reference": "FACT-BANK",
            "amount": "10.00",
            "description": "Frais bancaires fictifs",
            "counterparty": "Banque",
            "accounting_account": "627000",
            "bank_account_id": 1,
            "deductible_percentage": "100.00",
            "fiscal_treatment": "DEDUCTIBLE",
        },
    )
    assert operation.status_code == 201, operation.text
    refused = client.patch(
        "/api/operations/banks/1",
        json={"account_number": "512000", "reason": "Retour au compte d’origine"},
    )
    assert refused.status_code == 409
    assert _code(refused) == "BANK_HAS_MOVEMENTS"


def test_delete_is_refused_and_an_unchanged_patch_is_empty(client):
    assert client.post("/api/assets", json=furniture()).status_code == 201
    assert (
        client.post(
            "/api/operations/loans",
            json={
                "property_id": 1,
                "lender": "Banque fictive",
                "start_date": "2025-01-01",
                "initial_principal": "1000.00",
                "interest_rate": "1.00",
                "duration_months": 12,
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/operations/banks",
            json={"name": "Banque fictive", "account_number": "512000"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/operations/properties/1/tenants",
            json={"name": "Locataire fictif", "monthly_rent": "700.00", "entry_date": "2025-01-01"},
        ).status_code
        == 201
    )
    for path in (
        "/api/assets/1",
        "/api/operations/loans/1",
        "/api/operations/properties/1",
        "/api/operations/properties/1/tenants/1",
        "/api/operations/banks/1",
    ):
        assert client.delete(path).status_code == 405
    assert client.get("/api/assets").json()[0]["label"] == "Mobilier fictif"
    empty = client.patch(
        "/api/assets/1",
        json={"useful_life_months": 60, "reason": "Aucun changement réel"},
    )
    assert empty.status_code == 422
    assert _code(empty) == "CORRECTION_EMPTY"
