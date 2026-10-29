import pytest
from fastapi import HTTPException

from app.core.api_errors import (
    RESOLUTION_ACTIONS,
    _detail,
    fail,
    import_line_fail,
    validation_issues,
)


def test_detail_adds_resolution_action_when_known() -> None:
    payload = _detail("ACTIVITY_REQUIRED", "Créez l’activité.")
    assert payload["action"] == RESOLUTION_ACTIONS["ACTIVITY_REQUIRED"]


def test_import_line_fail_sets_location_and_line() -> None:
    with pytest.raises(HTTPException) as exc:
        import_line_fail("CSV_AMOUNT", "Montant invalide, ligne 4.", 4)
    detail = exc.value.detail
    assert detail["line"] == 4
    assert detail["location"] == "import"
    assert detail["code"] == "CSV_AMOUNT"


def test_validation_issues_map_pydantic_locations() -> None:
    issues = validation_issues(
        [
            {
                "type": "missing",
                "loc": ("body", "piece_reference"),
                "msg": "Field required",
            }
        ]
    )
    assert issues[0]["field"] == "piece_reference"
    assert issues[0]["location"] == "body"
    assert issues[0]["code"] == "missing"


def test_fail_can_override_field() -> None:
    with pytest.raises(HTTPException) as exc:
        fail("BANK_REQUIRED", "Banque requise.", 422, field="bank_account_id")
    assert exc.value.detail["field"] == "bank_account_id"
