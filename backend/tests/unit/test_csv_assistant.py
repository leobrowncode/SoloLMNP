"""French CSV assistant: templates, mapping, money, dates, and rejects."""

from app.domain.csv_assistant import (
    OPERATION_TYPE_ACCOUNTS,
    analyze,
    inspect_content,
    rejects_csv,
    template_csv,
)
from app.services.operations import OPERATION_TYPE_ACCOUNTS as ENGINE_ACCOUNTS


def test_type_accounts_match_the_posting_engine() -> None:
    assert OPERATION_TYPE_ACCOUNTS == ENGINE_ACCOUNTS


def test_templates_are_french_csv_with_examples() -> None:
    bank = template_csv("bank")
    operations = template_csv("operations")
    loans = template_csv("loan_payments")
    assert bank.startswith("\ufeffDate;Libellé;Montant;Référence\n")
    assert "800,00" in bank and "-42,50" in bank and "05/03/2026" in bank
    assert "kind" not in operations.splitlines()[0]
    assert operations.startswith("\ufeffNature;Date;Date de la pièce;")
    assert "Recette" in operations and "Dépense" in operations
    assert "piece_date" not in loans
    assert loans.startswith("\ufeffPrêt;Rang;Date;Date de débit;Capital;")
    assert "800,00" in loans


def test_template_rows_are_valid_before_the_accounting_year_check() -> None:
    for profile in ("bank", "operations", "loan_payments"):
        preview = analyze(profile, template_csv(profile), None)
        assert preview["ready"] is True
        assert preview["summary"]["error"] == 0
        assert preview["summary"]["valid"] == 2
        assert preview["delimiter"] == ";"


def test_french_amount_date_bom_and_user_mapping() -> None:
    content = (
        "\ufeffQuand;Texte;Somme;Identifiant\n"
        "05/03/2026;Loyer mars;1 234,56;REL-1\n"
        "06/03/2026;Note;1.234,50;REL-2\n"
    )
    inspected = inspect_content(content)
    assert inspected["headers"] == ["Quand", "Texte", "Somme", "Identifiant"]
    unmapped = analyze("bank", content, None)
    assert unmapped["ready"] is False
    assert unmapped["issues"][0]["column"] == "Date"
    assert unmapped["issues"][0]["correction"]
    mapped = analyze(
        "bank",
        content,
        {"date": "Quand", "label": "Texte", "amount": "Somme", "reference": "Identifiant"},
    )
    assert mapped["summary"] == {
        "valid": 2,
        "duplicate": 0,
        "warning": 0,
        "error": 0,
        "count": 2,
        "importable": 2,
    }
    assert mapped["rows"][0]["values"]["amount"] == "1234.56"
    assert mapped["rows"][0]["values"]["date"] == "2026-03-05"
    assert mapped["rows"][0]["display"]["date"] == "05/03/2026"
    assert mapped["rows"][1]["values"]["amount"] == "1234.50"


def test_rejection_names_the_row_column_value_and_correction() -> None:
    content = (
        "Date;Libellé;Montant;Référence\n31/02/2026;Loyer;abc;REL-1\n05/03/2026;Loyer;0,00;REL-2\n"
    )
    preview = analyze("bank", content, None)
    assert preview["summary"]["error"] == 2
    first = preview["rows"][0]["issues"]
    assert {issue["field"] for issue in first} >= {"date", "amount"}
    amount = next(issue for issue in first if issue["field"] == "amount")
    assert amount["line"] == 2
    assert amount["column"] == "Montant"
    assert amount["value"] == "abc"
    assert "800,00" in amount["correction"]
    assert amount["location"] == "import"
    assert amount["help"] == "import-csv"
    rejects = rejects_csv("bank", preview["rows"])
    assert rejects.startswith("\ufeff")
    assert "Correction" in rejects.splitlines()[0]
    assert "abc" in rejects
    assert "REL-1" in rejects
    assert "REL-2" in rejects


def test_tab_paste_decimal_comma_and_duplicate_reference() -> None:
    content = (
        "Nature\tDate\tType\tTiers\tMontant\tLibellé\tRéférence de pièce\n"
        "Recette\t05/03/2026\tLoyer\tDupont\t800,00\tLoyer mars\tLOY-1\n"
        "Dépense\t06/03/2026\tASS\tAssureur\t12,5\tAssurance\tLOY-1\n"
    )
    preview = analyze("operations", content, None)
    assert preview["delimiter"] == "\t"
    assert preview["rows"][0]["values"]["kind"] == "REVENUE"
    assert preview["rows"][0]["values"]["type"] == "LOY"
    assert preview["rows"][0]["values"]["accounting_account"] == "706000"
    assert preview["rows"][0]["status"] == "error"
    assert preview["rows"][1]["values"]["amount"] == "12.50"
    assert any(issue["code"] == "CSV_REFERENCE" for issue in preview["rows"][1]["issues"])
    warning_columns = {item["column"] for item in preview["rows"][0]["warnings"]}
    assert warning_columns == {"Date de la pièce", "Justificatif"}


def test_loan_split_error_keeps_the_other_columns() -> None:
    content = (
        "Prêt;Date;Capital;Intérêts;Assurance banque;Total banque\n"
        "PRET;05/03/2026;450,00;310,00;40,00;100,00\n"
    )
    preview = analyze("loan_payments", content, None)
    row = preview["rows"][0]
    assert row["status"] == "error"
    issue = next(item for item in row["issues"] if item["code"] == "LOAN_CSV_SPLIT")
    assert issue["column"] == "Total banque"
    assert issue["value"] == "100,00"
    assert issue["help"] == "emprunt"
    assert "ventilation" in issue["correction"]
