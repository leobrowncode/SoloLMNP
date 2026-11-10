"""Contrôles FEC de l'article A47 A-1 et des comptes rendus publics de Test Compta Demat.

L'outil officiel DGFiP (Test Compta Demat) est un exécutable Windows. Il n'a pas
été lancé ici. Ce module rejoue les règles publiées : dix-huit zones, tabulation,
CRLF, dates AAAAMMJJ, montants à virgule, équilibre, paires auxiliaire / lettrage /
devise, cohérence d'une même écriture. Débit et crédit tous deux renseignés, ou
tous deux nuls, est un avertissement : les comptes rendus publics de l'outil ne
le classent pas bloquant.
"""

from __future__ import annotations

import hashlib
from datetime import date

from app.domain.filing.fec import COLUMNS

OUTIL_OFFICIEL = (
    "Test Compta Demat (DGFiP) n'a pas ete execute : l'outil est Windows. "
    "Le validateur rejoue l'article A47 A-1 du LPF et les controles bloquants "
    "decrits par les comptes rendus publics de cet outil."
)

_OBLIGATOIRES = (
    "JournalCode",
    "JournalLib",
    "EcritureNum",
    "EcritureDate",
    "CompteNum",
    "CompteLib",
    "EcritureLib",
    "Debit",
    "Credit",
    "ValidDate",
)
_PAIRES = (
    ("CompAuxNum", "CompAuxLib", "AUXILIAIRE"),
    ("EcritureLet", "DateLet", "LETTRAGE"),
    ("Montantdevise", "Idevise", "DEVISE"),
)


def controler(payload: bytes, debut: date, fin: date) -> dict[str, object]:
    """0 anomalie bloquante est le critère CA3. Les avertissements ne bloquent pas."""
    bloquantes: list[dict[str, str]] = []
    avertissements: list[dict[str, str]] = []
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        bloquantes.append({"code": "ENCODAGE", "message": "Le FEC n'est pas de l'UTF-8."})
        return _rapport(bloquantes, avertissements, payload)
    if "\r\n" not in text or "\n" in text.replace("\r\n", ""):
        bloquantes.append(
            {"code": "SEPARATEUR", "message": "Les enregistrements sont séparés par CR LF."}
        )
    lignes = text.split("\r\n")
    if lignes and lignes[-1] == "":
        lignes = lignes[:-1]
    if not lignes or lignes[0].split("\t") != list(COLUMNS):
        bloquantes.append(
            {"code": "ENTETE", "message": "En-tête absent ou pas dans l'ordre A47 A-1."}
        )
        return _rapport(bloquantes, avertissements, payload)
    parsed: list[tuple[int, dict[str, str]]] = []
    for index, raw in enumerate(lignes[1:], start=2):
        cells = raw.split("\t")
        if len(cells) != 18:
            bloquantes.append({"code": "COLONNES", "message": f"Ligne {index} : 18 champs."})
            continue
        row = dict(zip(COLUMNS, cells, strict=True))
        parsed.append((index, row))
        _ligne(index, row, debut, fin, bloquantes, avertissements)
    _ecritures(parsed, debut, fin, bloquantes, avertissements)
    if parsed and not any(row["JournalCode"] == "AN" for _index, row in parsed):
        avertissements.append(
            {
                "code": "AN_ABSENT",
                "message": "Pas d'à-nouveaux. Attendu seulement au premier exercice.",
            }
        )
    return _rapport(bloquantes, avertissements, payload)


def _ligne(
    index: int,
    row: dict[str, str],
    debut: date,
    fin: date,
    bloquantes: list[dict[str, str]],
    avertissements: list[dict[str, str]],
) -> None:
    for name in _OBLIGATOIRES:
        if not row[name]:
            bloquantes.append({"code": "OBLIGATOIRE", "message": f"Ligne {index} : {name} vide."})
    for field in ("EcritureDate", "PieceDate", "ValidDate"):
        if row[field] and _date(row[field]) is None:
            bloquantes.append({"code": "DATE", "message": f"Ligne {index} : {field} invalide."})
    debit = _montant(row["Debit"])
    credit = _montant(row["Credit"])
    debit_illisible = bool(row["Debit"]) and debit is None
    credit_illisible = bool(row["Credit"]) and credit is None
    if debit_illisible or credit_illisible:
        bloquantes.append(
            {"code": "MONTANT", "message": f"Ligne {index} : montant hors format virgule."}
        )
    if debit and credit:
        avertissements.append(
            {
                "code": "DEUX_SENS",
                "message": f"Ligne {index} : débit et crédit tous deux renseignés.",
            }
        )
    elif debit == 0 and credit == 0 and row["Debit"] and row["Credit"]:
        avertissements.append(
            {"code": "MONTANT_NUL", "message": f"Ligne {index} : débit et crédit nuls."}
        )
    jour = _date(row["EcritureDate"])
    if jour is not None and not debut <= jour <= fin:
        bloquantes.append({"code": "HORS_EXERCICE", "message": f"Ligne {index} hors exercice."})
    for left, right, code in _PAIRES:
        if bool(row[left]) != bool(row[right]):
            bloquantes.append(
                {"code": code, "message": f"Ligne {index} : {left} et {right} vont ensemble."}
            )
        if code == "LETTRAGE" and row[right] and _date(row[right]) is None:
            bloquantes.append({"code": "DATE", "message": f"Ligne {index} : DateLet invalide."})


def _ecritures(
    parsed: list[tuple[int, dict[str, str]]],
    debut: date,
    fin: date,
    bloquantes: list[dict[str, str]],
    avertissements: list[dict[str, str]],
) -> None:
    del debut, fin
    groupes: dict[str, list[dict[str, str]]] = {}
    for _index, row in parsed:
        groupes.setdefault(row["EcritureNum"], []).append(row)
    precedent: date | None = None
    for number, group in groupes.items():
        debit = sum(_montant(row["Debit"]) or 0 for row in group)
        credit = sum(_montant(row["Credit"]) or 0 for row in group)
        if debit != credit:
            bloquantes.append(
                {"code": "DESEQUILIBRE", "message": f"Écriture {number} déséquilibrée."}
            )
        journaux = {row["JournalCode"] for row in group}
        dates = {row["EcritureDate"] for row in group}
        if len(journaux) > 1 or len(dates) > 1:
            bloquantes.append(
                {
                    "code": "ECRITURE_HETEROGENE",
                    "message": f"Écriture {number} : journal ou date incohérent.",
                }
            )
        jour = _date(group[0]["EcritureDate"])
        if jour is not None and precedent is not None and jour < precedent:
            avertissements.append(
                {
                    "code": "ORDRE",
                    "message": f"Écriture {number} : la date recule par rapport à la précédente.",
                }
            )
        if jour is not None:
            precedent = jour


def _montant(value: str) -> int | None:
    if not value or "," not in value:
        return None
    whole, fractional = value.split(",", 1)
    if not whole.isdigit() or len(fractional) != 2 or not fractional.isdigit():
        return None
    return int(whole) * 100 + int(fractional)


def _date(value: str) -> date | None:
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def _rapport(
    bloquantes: list[dict[str, str]],
    avertissements: list[dict[str, str]],
    payload: bytes,
) -> dict[str, object]:
    return {
        "bloquantes": bloquantes,
        "avertissements": avertissements,
        "valide": not bloquantes,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "outil_officiel": OUTIL_OFFICIEL,
    }
