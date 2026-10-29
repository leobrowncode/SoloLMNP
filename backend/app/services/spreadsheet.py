"""Read-only workbook of an exercise, to open in Google Sheets or a spreadsheet tool."""

import io
import zipfile
from decimal import Decimal
from typing import Any
from xml.sax.saxutils import escape

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BusinessOperation, DepreciationPeriod, Property
from app.services.efi import efi_worksheet
from app.services.ledger import get_year, projection
from app.services.operations import operation_json

FIXED_TIME = (2000, 1, 1, 0, 0, 0)
KINDS = {
    "REVENUE": "Recette",
    "EXPENSE": "Dépense",
    "SETTLEMENT": "Règlement",
    "LOAN_FUNDING": "Déblocage",
    "LOAN_PAYMENT": "Échéance",
}
Cell = str | Decimal | int | None


def year_workbook(session: Session, year_id: int) -> dict[str, Any]:
    year = get_year(session, year_id)
    sheets: list[tuple[str, list[list[Cell]]]] = [
        ("Opérations", _operations(session, year_id)),
        ("Journal", _journal(session, year_id)),
        ("Balance", _balance(session, year_id)),
        ("Amortissements", _depreciation(session, year_id)),
        ("Liasse", _liasse(session, year_id)),
    ]
    return {"filename": f"SoloLMNP-{year.year}.xlsx", "content": workbook(sheets)}


def _operations(session: Session, year_id: int) -> list[list[Cell]]:
    names = {row.id: row.name for row in session.scalars(select(Property))}
    rows: list[list[Cell]] = [
        [
            "Date",
            "Nature",
            "Bien",
            "Tiers",
            "Libellé",
            "Compte",
            "Montant",
            "Reste à régler",
            "Capital",
            "Intérêts",
            "Assurance",
            "Autres frais",
            "État",
        ]
    ]
    for row in session.scalars(
        select(BusinessOperation)
        .where(BusinessOperation.fiscal_year_id == year_id)
        .order_by(BusinessOperation.date, BusinessOperation.id)
    ):
        data = operation_json(session, row)
        rows.append(
            [
                data["date"],
                KINDS.get(row.kind, row.kind),
                names.get(row.property_id, ""),
                data["counterparty"],
                data["description"],
                data["accounting_account"],
                Decimal(data["amount"]),
                Decimal(data["remaining_to_settle"]) if data["remaining_to_settle"] else None,
                Decimal(data["principal"]),
                Decimal(data["interest"]),
                Decimal(data["insurance"]),
                Decimal(data["other_costs"]),
                "Extournée" if data["status"] == "REVERSED" else "Comptabilisée",
            ]
        )
    return rows


def _journal(session: Session, year_id: int) -> list[list[Cell]]:
    rows: list[list[Cell]] = [
        ["N°", "Date", "Journal", "Pièce", "Libellé", "Compte", "Libellé compte", "Débit", "Crédit"]
    ]
    for line in projection(session, year_id)["ledger"]:
        rows.append(
            [
                line["entry_number"],
                line["date"],
                line["journal_code"],
                line["piece_reference"],
                line["label"],
                line["account_number"],
                line["account_label"],
                Decimal(line["debit"]),
                Decimal(line["credit"]),
            ]
        )
    return rows


def _balance(session: Session, year_id: int) -> list[list[Cell]]:
    rows: list[list[Cell]] = [
        ["Compte", "Libellé", "Total débit", "Total crédit", "Solde débiteur", "Solde créditeur"]
    ]
    for row in projection(session, year_id)["balance"]:
        rows.append(
            [
                row["account_number"],
                row["label"],
                Decimal(row["total_debit"]),
                Decimal(row["total_credit"]),
                Decimal(row["debit_balance"]),
                Decimal(row["credit_balance"]),
            ]
        )
    return rows


def _depreciation(session: Session, year_id: int) -> list[list[Cell]]:
    from app.api.assets import period_json

    rows: list[list[Cell]] = [
        ["Élément", "Base", "Début", "Fin", "Jours", "Dotation", "Cumul", "Valeur nette", "État"]
    ]
    for period in session.scalars(
        select(DepreciationPeriod)
        .where(DepreciationPeriod.fiscal_year_id == year_id)
        .order_by(DepreciationPeriod.id)
    ):
        data = period_json(session, period)
        rows.append(
            [
                data["target_label"],
                Decimal(data["base"]),
                data["period_start"],
                data["period_end"],
                data["days"],
                Decimal(data["amount"]),
                Decimal(data["accumulated"]),
                Decimal(data["net_book_value"]),
                "Comptabilisée" if data["status"] == "POSTED" else "Calculée",
            ]
        )
    return rows


def _liasse(session: Session, year_id: int) -> list[list[Cell]]:
    try:
        sheet = efi_worksheet(session, year_id)
    except HTTPException as exc:
        detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
        return [["Liasse non disponible"], [str(detail.get("message", "Calcul fiscal absent."))]]
    rows: list[list[Cell]] = [
        ["Statut", str(sheet.get("output_headline") or sheet.get("output_label") or "Recherche")],
        [],
        ["Formulaire", "Case", "Libellé", "Montant"],
    ]
    for field in sheet["liasse"]["fields"]:
        rows.append(
            [
                field["form_ref"],
                field["official_case"],
                field["label"],
                Decimal(field["value"]),
            ]
        )
    personal = sheet["personal_return"]
    for line in personal.get("lines", []):
        rows.append([personal["form"], line["case"], line["label"], Decimal(line["amount"])])
    for row in personal.get("prior_deficits", []):
        rows.append(
            [
                personal["form"],
                row.get("case"),
                f"Déficit LMNP {row['origin_year']} non imputé",
                Decimal(row["amount"]),
            ]
        )
    tracking = sheet.get("depreciation_tracking")
    if tracking:
        rows.extend(
            [
                [],
                ["Suivi des amortissements non déduits (art. 39 C)"],
                ["Dotation comptable", Decimal(tracking["accounting_depreciation"])],
                ["Plafond", Decimal(tracking["capacity"])],
                ["Déduite cette année", Decimal(tracking["deducted_current"])],
                ["Non déduite (ligne 318)", Decimal(tracking["deferred_current"])],
                ["Reprise antérieure (ligne 350)", Decimal(tracking["prior_used"])],
                ["Stock total reporté", Decimal(tracking["remaining_total"])],
            ]
        )
    for item in sheet.get("blocking", []):
        rows.append(["Bloquant", item["message"]])
    return rows


def workbook(sheets: list[tuple[str, list[list[Cell]]]]) -> bytes:
    """Minimal Office Open XML workbook: inline strings, numbers, frozen header row."""
    names = [name[:31] for name, _ in sheets]
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/'
                'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for index in range(1, len(sheets) + 1)
            )
            + "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            "<sheets>"
            + "".join(
                f'<sheet name="{escape(name, {chr(34): "&quot;"})}" sheetId="{index}" '
                f'r:id="rId{index}"/>'
                for index, name in enumerate(names, 1)
            )
            + "</sheets></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/'
                f'officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/sheet{index}.xml"/>'
                for index in range(1, len(sheets) + 1)
            )
            + "</Relationships>"
        ),
    }
    for index, (_name, rows) in enumerate(sheets, 1):
        files[f"xl/worksheets/sheet{index}.xml"] = _sheet_xml(rows)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, content in files.items():
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, content.encode("utf-8"))
    return buffer.getvalue()


def _sheet_xml(rows: list[list[Cell]]) -> str:
    body = []
    for row_index, row in enumerate(rows, 1):
        cells = []
        for column, value in enumerate(row):
            if value is None or value == "":
                continue
            ref = f"{_column(column)}{row_index}"
            if isinstance(value, Decimal | int):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        body.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f"<sheetData>{''.join(body)}</sheetData></worksheet>"
    )


def _column(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name
