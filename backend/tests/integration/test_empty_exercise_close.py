"""Closing must not treat a property-free, entry-free year as complete."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_precheck_blocks_an_empty_exercise(settings, database) -> None:
    del database
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as client:
        activity = client.post(
            "/api/ledger/activity",
            json={"activity_name": "Essai", "activity_start_date": "2025-04-06"},
        )
        assert activity.status_code == 201, activity.text
        year = client.post(
            "/api/ledger/years",
            json={
                "year": 2025,
                "start_date": "2025-04-06",
                "end_date": "2025-12-31",
                "fiscal_vintage": "2025",
            },
        )
        assert year.status_code == 201, year.text
        precheck = client.get("/api/filing/years/1/precheck")
        assert precheck.status_code == 200, precheck.text
        codes = [item["code"] for item in precheck.json()["errors"]]
        assert "EMPTY_EXERCISE" in codes
        assert precheck.json()["blocking"] is True
