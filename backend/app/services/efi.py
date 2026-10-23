"""Manual EFI worksheet. Nothing is sent to the tax authority."""

import json
import textwrap
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.filing.mappings import BLOCKING_WARNINGS, compile_package
from app.models.filing import TaxReturnSnapshot
from app.services.ledger import get_year

FORM_ORDER = ("2031-SD", "2031-BIS-SD", "2033-A-SD", "2033-B-SD", "2033-C-SD", "2033-E-SD")
FORM_TITLES = {
    "2031-SD": "2031-SD — déclaration de résultat BIC",
    "2031-BIS-SD": "2031-bis-SD — BIC non professionnels",
    "2033-A-SD": "2033-A — bilan simplifié",
    "2033-B-SD": "2033-B — compte de résultat et résultat fiscal",
    "2033-C-SD": "2033-C — immobilisations et amortissements",
    "2033-E-SD": "2033-E — valeur ajoutée",
}


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
    declarable = bool(package.get("declarable"))
    blocking = [
        *package.get("errors", []),
        *[item for item in package.get("warnings", []) if item["code"] in BLOCKING_WARNINGS],
    ]
    return {
        "fiscal_year_id": year.id,
        "year": year.year,
        "declarable": declarable,
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
        "exercise": copy.get(
            "exercise",
            {"start": year.start_date.isoformat(), "end": year.end_date.isoformat()},
        ),
        "instructions": copy.get("instructions", []),
        "depreciation_tracking": copy.get("depreciation_tracking"),
        "blocking": blocking,
        "warnings": [
            item for item in package.get("warnings", []) if item["code"] not in BLOCKING_WARNINGS
        ],
        "by_property": package.get("by_property", []),
        "disclaimer": (
            "Feuille prête à recopier dans votre espace professionnel impots.gouv.fr. "
            "Aucun envoi n’est effectué par SoloLMNP."
            if declarable
            else "Feuille non prête : corrigez les points bloquants avant de la recopier. "
            "Aucun envoi n’est effectué par SoloLMNP."
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
        "personal_return": package.get("personal_return")
        or {
            "form": "2042-C-PRO",
            "status": "case_not_verified",
            "separated_from_liasse": True,
            "lines": [],
            "prior_deficits": [],
            "note": "",
        },
    }


def worksheet_pdf(worksheet: dict[str, Any]) -> bytes:
    lines: list[tuple[str, bool]] = []

    def title(text: str) -> None:
        lines.append(("", False))
        lines.append((text, True))

    def text(value: str) -> None:
        for chunk in textwrap.wrap(value, 100) or [""]:
            lines.append((chunk, False))

    exercise = worksheet.get("exercise") or {}
    declarant = worksheet.get("declarant") or {}
    status = (
        "prête à recopier (ready)"
        if worksheet.get("declarable")
        else "non prête (" + str(worksheet.get("status", "research_only")) + ")"
    )
    lines.append(
        (
            "SoloLMNP — liasse LMNP à recopier — exercice du "
            f"{_fr(exercise.get('start'))} au {_fr(exercise.get('end'))}",
            True,
        )
    )
    text(f"Statut : {status}. Aucune transmission : à recopier soi-même en mode EFI.")
    text(
        f"Déclarant : {declarant.get('name') or '—'} · SIREN {declarant.get('siren') or 'manquant'}"
        f" · SIRET {declarant.get('siret') or '—'}"
    )
    frozen = "figée à la clôture" if worksheet.get("frozen") else "calcul en cours, non figée"
    text(f"Feuille {frozen}. Empreinte {worksheet.get('snapshot_sha256', '')}")
    if worksheet.get("vintage_note"):
        text(str(worksheet["vintage_note"]))
    if worksheet.get("blocking"):
        title("Points bloquants")
        for item in worksheet["blocking"]:
            text(f"- {item['message']}")
    if worksheet.get("instructions"):
        title("Consignes de saisie")
        for item in worksheet["instructions"]:
            text(f"- {item}")
    fields = worksheet["liasse"]["fields"]
    for form in FORM_ORDER:
        rows = [field for field in fields if field.get("form_ref") == form]
        if not rows:
            continue
        title(FORM_TITLES[form])
        for field in rows:
            case = field.get("official_case")
            prefix = f"Case {case} — " if case else ""
            text(f"{prefix}{field['label']} : {_euros(field['value'])}")
    tracking = worksheet.get("depreciation_tracking")
    if tracking:
        title("État de suivi des amortissements non déduits (art. 39 C II du CGI)")
        text(
            f"Dotation comptable {_euros(tracking['accounting_depreciation'])} · plafond "
            f"{_euros(tracking['capacity'])} · déduite {_euros(tracking['deducted_current'])} · "
            f"non déduite de l’exercice (ligne 318) {_euros(tracking['deferred_current'])}"
        )
        text(f"Reprise d’amortissements antérieurs (ligne 350) : {_euros(tracking['prior_used'])}")
        for row in tracking.get("prior", []):
            text(
                f"- Origine {row['origin_year']} : stock {_euros(row['opening'])}, "
                f"repris {_euros(row['used'])}, reste {_euros(row['remaining'])}"
            )
        text(f"Stock total reporté en fin d’exercice : {_euros(tracking['remaining_total'])}")
    personal = worksheet.get("personal_return") or {}
    if personal.get("lines"):
        title("2042-C-PRO — déclaration de revenus du foyer (à part de la liasse)")
        for line in personal["lines"]:
            text(
                f"Case {line['case']} (déclarant 2 : {line['case_declarant_2']}) — "
                f"{line['label']} : {_euros(line['amount'])}"
            )
        for row in personal.get("prior_deficits", []):
            case = row.get("case") or "case à vérifier"
            text(
                f"Case {case} — déficit LMNP {row['origin_year']} restant : {_euros(row['amount'])}"
            )
        if personal.get("note"):
            text(str(personal["note"]))
    properties = worksheet.get("by_property") or []
    if properties:
        title("Répartition par bien (information)")
    for row in properties:
        text(
            f"{row['name']} : loyers {_euros(row['rents'])}, charges {_euros(row['expenses'])}, "
            f"dotations {_euros(row['depreciation'])}"
        )
    return _plain_pdf(lines)


def _fr(value: object) -> str:
    if not isinstance(value, str):
        return "—"
    try:
        return date.fromisoformat(value).strftime("%d/%m/%Y")
    except ValueError:
        return value


def _euros(value: object) -> str:
    raw = str(value)
    negative = raw.startswith("-")
    whole, _, cents = raw.lstrip("-").partition(".")
    grouped = f"{int(whole or '0'):,}".replace(",", " ")
    return f"{'-' if negative else ''}{grouped},{(cents or '00')[:2].ljust(2, '0')} €"


def _escape(value: str) -> bytes:
    encoded = value.replace("→", "->").encode("cp1252", "replace")
    return encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _plain_pdf(lines: list[tuple[str, bool]]) -> bytes:
    per_page = 52
    pages = [lines[index : index + per_page] for index in range(0, max(len(lines), 1), per_page)]
    content_objects: list[bytes] = []
    for page in pages:
        commands = [b"BT", b"40 805 Td", b"14 TL"]
        for text, bold in page:
            commands.append(b"/F2 9 Tf" if bold else b"/F1 9 Tf")
            commands.append(b"(" + _escape(text) + b") Tj T*")
        commands.append(b"ET")
        content_objects.append(b"\n".join(commands))
    regular = 3 + len(pages) * 2
    bold_font = regular + 1
    kids = []
    objects: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    for content in content_objects:
        page_number = len(objects) + 1
        kids.append(f"{page_number} 0 R".encode())
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents "
            + str(page_number + 1).encode()
            + b" 0 R /Resources << /Font << /F1 "
            + str(regular).encode()
            + b" 0 R /F2 "
            + str(bold_font).encode()
            + b" 0 R >> >> >>"
        )
        objects.append(
            b"<< /Length "
            + str(len(content)).encode()
            + b" >>\nstream\n"
            + content
            + b"\nendstream"
        )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    )
    objects[1] = (
        b"<< /Type /Pages /Count "
        + str(len(pages)).encode()
        + b" /Kids ["
        + b" ".join(kids)
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
