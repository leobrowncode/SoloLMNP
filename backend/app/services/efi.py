"""Manual EFI worksheet. Nothing is sent to the tax authority."""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.filing.mappings import compile_package
from app.models.filing import TaxReturnSnapshot
from app.services.ledger import get_year


def efi_worksheet(session: Session, year_id: int) -> dict[str, Any]:
    year = get_year(session, year_id)
    snapshot = session.scalar(
        select(TaxReturnSnapshot).where(
            TaxReturnSnapshot.fiscal_year_id == year.id,
            TaxReturnSnapshot.status == "CURRENT",
        )
    )
    if snapshot is None:
        package = compile_package(session, year_id)
        frozen = False
        digest = package["ledger_sha256"]
    else:
        package = json.loads(snapshot.canonical_json)
        frozen = True
        digest = snapshot.sha256
    copy = package.get("copy") or {}
    return {
        "fiscal_year_id": year.id,
        "declarable": bool(package.get("declarable")),
        "status": package.get("status", "research_only"),
        "transmission": False,
        "frozen": frozen,
        "snapshot_sha256": digest,
        "portal": copy.get(
            "portal",
            "https://www.impots.gouv.fr/professionnel/teleprocedures-efi-ou-edi",
        ),
        "vintage_note": copy.get("vintage_note", ""),
        "declarant": copy.get("declarant"),
        "by_property": package.get("by_property", []),
        "disclaimer": (
            (
                "Feuille de l’exercice 2026, à recopier. Pas de déclaration 2025. "
                "Aucun envoi n’est effectué."
                if package.get("vintage") == "2026"
                else "Feuille prête à recopier. Aucun envoi n’est effectué."
            )
            if package.get("declarable")
            else (
                "Feuille de recopie non déclarable. Aucune case 2042-C-PRO n’est affirmée. "
                "Aucun envoi n’est effectué."
            )
        ),
        "liasse": {
            "form": package["form"],
            "vintage": package["vintage"],
            "fields": [
                {
                    "code": field["code"],
                    "form_ref": field.get("form_ref", package["form"]),
                    "official_case": field.get("official_case"),
                    "label": field["label"],
                    "value": field["value"],
                    "expression": field["expression"],
                    "rules": field.get("rules", []),
                    "accounts": field.get("accounts", []),
                    "entries": field.get("entries", []),
                }
                for field in package["fields"]
            ],
        },
        "personal_return": {
            "form": "2042-C-PRO",
            "official_case": None,
            "status": "case_not_verified",
            "amount": package["fiscal_result"],
            "separated_from_liasse": True,
        },
    }


def worksheet_pdf(worksheet: dict[str, Any]) -> bytes:
    frozen = "figee a la cloture" if worksheet.get("frozen") else "calcul en cours, non fige"
    lines = [
        "SoloLMNP - feuille de recopie - " + str(worksheet.get("status", "research_only")),
        "Transmission: non. Aucun envoi.",
        f"Exercice {worksheet['fiscal_year_id']} - {frozen}",
        f"Empreinte {worksheet['snapshot_sha256']}",
        worksheet.get("vintage_note") or "",
        "2042-C-PRO - case: non verifiee - montant "
        + worksheet["personal_return"]["amount"],
    ]
    for field in worksheet["liasse"]["fields"]:
        case = field.get("official_case") or "sans numero"
        form = field.get("form_ref") or ""
        lines.append(f"{form} case {case} - {field['label']} = {field['value']}")
    for row in worksheet.get("by_property") or []:
        lines.append(
            f"Bien {row['name']} loyers {row['rents']} charges {row['expenses']} "
            f"dotations {row['depreciation']}"
        )
    return _plain_pdf([line for line in lines if line])


def _plain_pdf(lines: list[str]) -> bytes:
    pages = [lines[index : index + 45] for index in range(0, max(len(lines), 1), 45)]
    page_objects: list[bytes] = []
    content_objects: list[bytes] = []
    for page in pages:
        commands = ["BT", "/F1 9 Tf", "40 800 Td"]
        for index, line in enumerate(page):
            if index:
                commands.append("0 -16 Td")
            encoded = line.encode("latin-1", "replace").decode("latin-1")
            escaped = encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj")
        commands.append("ET")
        content_objects.append("\n".join(commands).encode("latin-1"))
    font_number = 3 + len(pages) * 2
    kids = []
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
    ]
    for content in content_objects:
        page_number = len(objects) + 1
        content_number = page_number + 1
        kids.append(f"{page_number} 0 R".encode())
        page_objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents "
            + str(content_number).encode()
            + b" 0 R /Resources << /Font << /F1 "
            + str(font_number).encode()
            + b" 0 R >> >> >>"
        )
        objects.append(page_objects[-1])
        objects.append(
            b"<< /Length "
            + str(len(content)).encode()
            + b" >>\nstream\n"
            + content
            + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    kid_list = b" ".join(kids)
    objects[1] = (
        b"<< /Type /Pages /Count "
        + str(len(pages)).encode()
        + b" /Kids ["
        + kid_list
        + b"] >>"
    )
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode())
        payload.extend(body)
        payload.extend(b"\nendobj\n")
    xref = len(payload)
    payload.extend(f"xref\n0 {len(offsets)}\n".encode())
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(payload)
