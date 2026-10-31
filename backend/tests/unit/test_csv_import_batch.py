"""Operations CSV commit refuses a silent partial post."""

from app.domain.csv_import_batch import (
    batch_items,
    fingerprint,
    guard_operations_commit,
    paid_lines_need_bank,
    summarize_batch,
)


def _row(
    line: int,
    *,
    status: str = "valid",
    importable: bool = True,
    paid: bool = False,
    code: str = "CSV_INVALID",
    message: str = "Rejet.",
) -> dict:
    row: dict = {
        "line": line,
        "status": status,
        "importable": importable,
        "duplicate": status == "duplicate",
        "paid": paid,
        "values": {"piece_reference": f"P-{line}"},
        "issues": [],
        "warnings": [],
    }
    if status == "error":
        row["issues"] = [{"code": code, "message": message, "line": line}]
        row["importable"] = False
    return row


def test_paid_lines_without_a_bank_block_before_any_posting() -> None:
    rows = [_row(2, paid=True), _row(3, status="error", paid=False)]
    assert paid_lines_need_bank(rows, None) is True
    assert paid_lines_need_bank(rows, 1) is False
    blocked = guard_operations_commit(rows, bank_account_id=None, import_valid_only=True)
    assert blocked["ok"] is False
    assert blocked["code"] == "BANK_REQUIRED"
    assert "Rien n’a été comptabilisé" in blocked["message"]
    assert "importable" not in blocked


def test_rejects_are_not_posted_unless_the_caller_accepts_them() -> None:
    rows = [
        _row(2, status="error", code="DATE_OUTSIDE_YEAR", message="Date hors exercice."),
        _row(3),
    ]
    refused = guard_operations_commit(rows, bank_account_id=1, import_valid_only=False)
    assert refused["ok"] is False
    assert refused["code"] == "CSV_PARTIAL_REFUSED"
    assert refused["message"].startswith("1 ligne est rejetée.")
    assert "seules lignes valides" in refused["message"]
    accepted = guard_operations_commit(rows, bank_account_id=1, import_valid_only=True)
    assert accepted["ok"] is True
    assert [row["line"] for row in accepted["importable"]] == [3]


def test_a_file_with_only_rejects_asks_for_a_correction() -> None:
    rows = [_row(2, status="error"), _row(3, status="error")]
    refused = guard_operations_commit(rows, bank_account_id=1, import_valid_only=False)
    assert refused["code"] == "CSV_PARTIAL_REFUSED"
    assert "2 lignes sont rejetées." in refused["message"]
    assert "Corrigez le fichier avant de comptabiliser." in refused["message"]
    empty = guard_operations_commit(rows, bank_account_id=1, import_valid_only=True)
    assert empty["ok"] is False
    assert empty["code"] == "CSV_INVALID"


def test_batch_counts_posted_rejected_and_skipped_lines() -> None:
    rows = [
        _row(2),
        _row(3, status="duplicate", importable=False),
        _row(4, status="error", message="Montant invalide."),
    ]
    items = batch_items(rows)
    summary = summarize_batch("operations-csv-1", items, replayed=False)
    assert summary["posted_count"] == 1
    assert summary["rejected_count"] == 1
    assert summary["skipped_count"] == 1
    assert summary["items"][0]["piece_reference"] == "P-2"
    assert summary["items"][2]["message"] == "Montant invalide."
    assert summary["replayed"] is False


def test_duplicates_and_non_importable_warnings_are_not_posted() -> None:
    duplicates = [_row(2, status="duplicate", importable=False)]
    empty = guard_operations_commit(duplicates, bank_account_id=1, import_valid_only=False)
    assert empty["code"] == "CSV_EMPTY"
    warning = _row(3, status="warning", importable=False)
    warning["warnings"] = [{"code": "DATE_OUTSIDE_YEAR", "message": "Hors exercice."}]
    skipped = batch_items([warning])[0]
    assert skipped["status"] == "skipped"
    assert skipped["code"] == "DATE_OUTSIDE_YEAR"
    assert skipped["message"] == "Hors exercice."


def test_fingerprint_changes_when_the_file_or_the_choice_changes() -> None:
    base = fingerprint(
        content="a",
        mapping={"date": "Date"},
        property_id=1,
        fiscal_year_id=1,
        bank_account_id=1,
        import_valid_only=False,
    )
    same = fingerprint(
        content="a",
        mapping={"date": "Date"},
        property_id=1,
        fiscal_year_id=1,
        bank_account_id=1,
        import_valid_only=False,
    )
    chosen = fingerprint(
        content="a",
        mapping={"date": "Date"},
        property_id=1,
        fiscal_year_id=1,
        bank_account_id=1,
        import_valid_only=True,
    )
    assert base == same
    assert base != chosen
