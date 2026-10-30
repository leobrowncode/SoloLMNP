"""Control archive of a closed exercise: FEC, its description and the copy sheet."""

import hashlib
import io
import json
import zipfile
from typing import Any

from sqlalchemy.orm import Session

from app.domain.filing.declaration import archival_csv, archival_json
from app.domain.filing.fec import export_fec, fec_description
from app.services.efi import efi_worksheet, worksheet_pdf

FIXED_TIME = (2000, 1, 1, 0, 0, 0)


def control_archive(session: Session, year_id: int) -> dict[str, Any]:
    rendered = export_fec(session, year_id)
    worksheet = efi_worksheet(session, year_id)
    stem = rendered["filename"].removesuffix(".txt")
    year = rendered["end_date"].year
    files: list[tuple[str, bytes]] = [
        (rendered["filename"], rendered["content"]),
        (f"{stem}_description.txt", fec_description(rendered).encode("utf-8")),
        (f"liasse-{year}.pdf", worksheet_pdf(worksheet)),
        (
            f"liasse-{year}.json",
            json.dumps(worksheet, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        ),
        (f"efi-{year}.json", archival_json(worksheet)[0]),
        (f"efi-{year}.csv", archival_csv(worksheet)[0]),
        ("LISEZMOI.txt", _readme(rendered, worksheet).encode("utf-8")),
    ]
    sums = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {name}\n" for name, content in files
    ).encode()
    files.append(("SHA256SUMS.txt", sums))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, content in files:
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, content)
    payload = buffer.getvalue()
    return {
        "filename": f"controle-{stem}.zip",
        "content": payload,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _readme(rendered: dict[str, Any], worksheet: dict[str, Any]) -> str:
    status = str(worksheet.get("output_headline") or worksheet.get("output_label") or "Recherche")
    return "\r\n".join(
        [
            "Dossier de contrôle SoloLMNP",
            "",
            f"Exercice du {rendered['start_date']:%d/%m/%Y} au {rendered['end_date']:%d/%m/%Y}"
            f" — SIREN {rendered['siren']}",
            "",
            f"{rendered['filename']} : fichier des écritures comptables (FEC), à remettre au",
            "  vérificateur sur demande en cas de contrôle (LPF art. L47 A).",
            "*_description.txt : description du FEC exigée par l’article A47 A-1 du LPF.",
            f"liasse-*.pdf et .json : feuille de recopie de la liasse ({status}),",
            "  figée à la clôture, avec l’état de suivi des amortissements non déduits.",
            "efi-*.json et efi-*.csv : export d’archivage, document de travail à vérifier,",
            "  avec le millésime et les versions de règles. Ce n’est pas un envoi.",
            "SHA256SUMS.txt : empreintes pour prouver que les fichiers n’ont pas changé.",
            "",
            "Conservez ce dossier, les justificatifs et l’accusé de dépôt impots.gouv.fr",
            "au moins six ans (LPF art. L102 B). SoloLMNP n’a rien transmis.",
            "",
        ]
    )
