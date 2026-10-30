"""Seed several years of fictional entries and time the read APIs.

Nothing is written under data/. The database stays in a temporary directory.
Page timings run only with --pages, after Playwright and Chromium are installed
in e2e/. This script is not part of CI.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app.api.ledger_schemas import EntryInput  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.database import Database  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.ledger import create_draft, post_entry  # noqa: E402

ENTRIES_PER_YEAR = 800
ASSET_COUNT = 40
YEARS = (
    (2024, date(2024, 1, 1), date(2024, 12, 31), 360),
    (2025, date(2025, 1, 1), date(2025, 12, 31), 360),
    (2026, date(2026, 1, 1), date(2026, 12, 31), 170),
)


def migration_config(settings: Settings) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["settings"] = settings
    return config


def seed_entries(database: Database, year_ids: dict[int, int]) -> int:
    written = 0
    session = database.sessions()
    try:
        for year, start, _end, span in YEARS:
            year_id = year_ids[year]
            for index in range(ENTRIES_PER_YEAR):
                when = start + timedelta(days=index % span)
                income = index % 2 == 0
                amount = f"{10 + (index % 50)}.00"
                debit = "512000" if income else "615000"
                credit = "706000" if income else "401000"
                label = "Loyer fictif" if income else "Entretien fictif"
                payload = EntryInput.model_validate(
                    {
                        "fiscal_year_id": year_id,
                        "journal_code": "OD",
                        "accounting_date": when,
                        "piece_reference": f"VOL-{year}-{index:04d}",
                        "piece_date": when,
                        "label": label,
                        "lines": [
                            {
                                "account_number": debit,
                                "label": label,
                                "debit": amount,
                                "credit": "0.00",
                            },
                            {
                                "account_number": credit,
                                "label": label,
                                "debit": "0.00",
                                "credit": amount,
                            },
                        ],
                    }
                )
                entry = create_draft(session, payload)
                post_entry(session, entry, entry.version)
                written += 1
                if written % 400 == 0:
                    session.commit()
                    print(f"écritures validées : {written}", flush=True)
        session.commit()
    finally:
        session.close()
    return written


def timed(client: TestClient, path: str) -> tuple[int, float, int]:
    engine = client.app.state.database.engine
    count = 0

    def before(*_args: object) -> None:
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", before)
    started = time.perf_counter()
    try:
        response = client.get(path)
    finally:
        event.remove(engine, "before_cursor_execute", before)
    elapsed = (time.perf_counter() - started) * 1000
    return response.status_code, elapsed, count


def explain(database_path: Path, sql: str) -> str:
    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
    finally:
        connection.close()
    return " | ".join(str(row[-1]) for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pages",
        action="store_true",
        help="Mesurer aussi l’affichage des pages (Playwright + Chromium).",
    )
    args = parser.parse_args()
    temporary = tempfile.mkdtemp(prefix="sololmnp-bench-")
    database_path = Path(temporary) / "bench.sqlite3"
    documents = Path(temporary) / "documents"
    documents.mkdir()
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{database_path.as_posix()}",
        documents_dir=documents,
        allowed_hosts=("testserver", "localhost", "127.0.0.1"),
    )
    command.upgrade(migration_config(settings), "head")
    app = create_app(settings)
    balance_year = 0
    with TestClient(app, headers={"X-SoloLMNP-Request": "1"}) as client:
        activity = client.post(
            "/api/ledger/activity",
            json={"activity_name": "Volume fictif", "activity_start_date": "2024-01-01"},
        )
        if activity.status_code != 201:
            raise SystemExit(activity.text)
        year_ids: dict[int, int] = {}
        for year, start, end, _span in YEARS:
            created = client.post(
                "/api/ledger/years",
                json={
                    "year": year,
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "fiscal_vintage": str(year),
                },
            )
            if created.status_code != 201:
                raise SystemExit(created.text)
            match = next(row for row in created.json()["years"] if row["year"] == year)
            year_ids[year] = int(match["id"])
        property_response = client.post(
            "/api/operations/properties",
            json={
                "name": "Immeuble fictif",
                "address": "1 rue du Volume",
                "acquisition_date": "2024-02-01",
                "acquisition_price": "100000.00",
                "land_value": "20000.00",
                "building_value": "80000.00",
            },
        )
        if property_response.status_code != 201:
            raise SystemExit(property_response.text)
        for index in range(ASSET_COUNT):
            asset = client.post(
                "/api/assets",
                json={
                    "property_id": 1,
                    "category": "FURNITURE",
                    "label": f"Mobilier fictif {index + 1}",
                    "acquisition_date": "2024-07-01",
                    "service_start_date": "2024-07-01",
                    "acquisition_value": "1200.00",
                    "depreciable_value": "1200.00",
                    "non_depreciable_value": "0.00",
                    "residual_value": "0.00",
                    "method": "LINEAR",
                    "useful_life_months": 60,
                    "asset_account": "218400",
                    "depreciation_account": "281840",
                    "basis_reason": f"Facture fictive MOB-{index + 1:03d}",
                    "duration_reason": "Durée d’utilisation estimée à cinq ans",
                },
            )
            if asset.status_code != 201:
                raise SystemExit(asset.text)
        started = time.perf_counter()
        written = seed_entries(client.app.state.database, year_ids)
        seed_seconds = time.perf_counter() - started
        target = year_ids[2025]
        balance_year = target
        paths = {
            "journal_page": f"/api/ledger/entries?fiscal_year_id={target}&status=VALIDATED&limit=50",
            "balance": f"/api/ledger/years/{target}/balance",
            "statements": f"/api/ledger/years/{target}/statements",
            "general_ledger_706000": (
                f"/api/ledger/years/{target}/general-ledger?account_number=706000"
            ),
            "assets": "/api/assets",
        }
        print(
            f"SEED years={len(YEARS)} entries={written} assets={ASSET_COUNT} "
            f"seed_s={seed_seconds:.1f}",
            flush=True,
        )
        for name, path in paths.items():
            timed(client, path)
            status, elapsed, queries = timed(client, path)
            print(f"API {name} status={status} ms={elapsed:.1f} sql={queries}", flush=True)
        fiscal = client.post(f"/api/fiscal/years/{target}", json={"adjustments": []})
        print(f"API fiscal_compute_2025 status={fiscal.status_code}", flush=True)
        if fiscal.status_code == 200:
            body = fiscal.json()
            print(
                "API fiscal_posture "
                f"status={body.get('status')} declarable={body.get('declarable')} "
                f"output_status={body.get('output_status')}",
                flush=True,
            )
            started = time.perf_counter()
            again = client.post(f"/api/fiscal/years/{target}", json={"adjustments": []})
            elapsed = (time.perf_counter() - started) * 1000
            print(
                f"API fiscal_compute_2025_repeat status={again.status_code} ms={elapsed:.1f}",
                flush=True,
            )
    print(
        "EXPLAIN journal "
        + explain(
            database_path,
            "SELECT id FROM accounting_entry "
            f"WHERE fiscal_year_id = {balance_year} AND status = 'VALIDATED' "
            "ORDER BY accounting_date, sequence, id LIMIT 50",
        ),
        flush=True,
    )
    print(
        "EXPLAIN balance "
        + explain(
            database_path,
            "SELECT accounting_entry_line.id FROM accounting_entry_line "
            "JOIN accounting_entry ON accounting_entry.id = accounting_entry_line.accounting_entry_id "
            "WHERE accounting_entry.fiscal_year_id = "
            f"{balance_year} AND accounting_entry.status = 'VALIDATED' "
            "ORDER BY accounting_entry.accounting_date, accounting_entry.sequence, "
            "accounting_entry_line.position",
        ),
        flush=True,
    )
    print(f"DATABASE {database_path}", flush=True)
    if not args.pages:
        return
    env = os.environ.copy()
    env["SOLOLMNP_VOLUME"] = "1"
    env["SOLOLMNP_E2E_DATABASE"] = str(database_path)
    env["PYTHON"] = sys.executable
    completed = subprocess.run(
        ["npm", "test", "--", "volume.spec.ts", "--retries=0"],
        cwd=ROOT / "e2e",
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
