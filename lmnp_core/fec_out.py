"""FEC à partir des écritures du noyau. Le validateur historique reste la référence de format."""

from __future__ import annotations

import hashlib
from datetime import date

from app.domain.accounting.chart import INITIAL_ACCOUNTS
from app.domain.filing.fec import COLUMNS, fec_description, fec_text, validate_fec

from lmnp_core.money import euros
from lmnp_core.posting import Ecriture

_LABELS = {number: label for number, label, _kind in INITIAL_ACCOUNTS}
_LABELS["120000"] = "Resultat de l'exercice"
_JOURNAUX = {
    "AN": "A-nouveaux",
    "OD": "Operations diverses",
    "BQ": "Banque",
    "AC": "Achats",
    "VE": "Ventes",
}


def render_fec(
    entries: list[Ecriture], *, siren: str, debut: date, fin: date
) -> dict[str, object]:
    rows: list[dict[str, str]] = []
    for entry in entries:
        if entry.journal == "CENTRALIZATION":
            continue
        for line in entry.lignes:
            if line.debit == 0 and line.credit == 0:
                continue
            if line.debit and line.credit:
                raise ValueError("Une ligne FEC n'a pas débit et crédit ensemble.")
            rows.append(
                {
                    "JournalCode": entry.journal,
                    "JournalLib": fec_text(_JOURNAUX[entry.journal]),
                    "EcritureNum": str(entry.numero),
                    "EcritureDate": entry.date.strftime("%Y%m%d"),
                    "CompteNum": line.compte,
                    "CompteLib": fec_text(_LABELS.get(line.compte, line.compte)),
                    "CompAuxNum": "",
                    "CompAuxLib": "",
                    "PieceRef": fec_text(entry.piece),
                    "PieceDate": entry.date.strftime("%Y%m%d"),
                    "EcritureLib": fec_text(line.libelle),
                    "Debit": _montant(line.debit),
                    "Credit": _montant(line.credit),
                    "EcritureLet": "",
                    "DateLet": "",
                    "ValidDate": entry.date.strftime("%Y%m%d"),
                    "Montantdevise": "",
                    "Idevise": "",
                }
            )
    payload = ("\t".join(COLUMNS) + "\r\n" + "".join(_format(row) for row in rows)).encode("utf-8")
    filename = f"{siren}FEC{fin.strftime('%Y%m%d')}.txt"
    rendered = {
        "filename": filename,
        "siren": siren,
        "start_date": debut,
        "end_date": fin,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "content": payload,
        "line_count": len(rows),
        "entry_count": len({row["EcritureNum"] for row in rows}),
        "validation": validate_fec(payload, debut, fin),
    }
    rendered["description"] = fec_description(rendered)
    return rendered


def _montant(cents: int) -> str:
    return euros(cents)


def _format(row: dict[str, str]) -> str:
    return "\t".join(row[column] for column in COLUMNS) + "\r\n"
