"""Sorties du jalon J3 : EFI, PDF, suivi, FEC contrôlé, archive."""

from __future__ import annotations

import json
from pathlib import Path

from lmnp_core.archive_out import zipper
from lmnp_core.build import Annee, Resultat
from lmnp_core.efi_sheet import feuille, texte
from lmnp_core.fec_rules import OUTIL_OFFICIEL, controler
from lmnp_core.pdf_out import pdf_texte
from lmnp_core.suivi import etat, lignes_texte
from lmnp_core.trace import traces_de

_LISEZMOI = """Dossier de sorties SoloLMNP.
Document de travail. A recopier soi-meme dans EFI (impots.gouv.fr).
Aucune teletransmission.

{outil}

SHA256SUMS.txt donne l'empreinte de chaque fichier.
""".strip()


def produire(resultat: Resultat) -> dict[str, object]:
    annee = _annee_liasse(resultat)
    traces = traces_de(annee.cases, annee.ecritures)
    sheet = feuille(annee.cases, traces)
    suivi = etat(resultat.annees)
    payload = annee.fec_texte.encode("utf-8")
    exercice = _exercice(resultat, annee)
    controle = controler(payload, exercice.debut, exercice.fin)
    efi_txt = texte(sheet, nom=resultat.dossier.nom, siret=resultat.dossier.siret).encode()
    liasse_pdf = pdf_texte(
        "Liasse a recopier",
        _lignes_pdf(sheet, hors="2042-C-PRO"),
    )
    pro_pdf = pdf_texte("2042-C-PRO", _lignes_pdf(sheet, seulement="2042-C-PRO"))
    suivi_pdf = pdf_texte("Etat de suivi 39 C", lignes_texte(suivi))
    description = annee.fec_description.encode("utf-8")
    readme = _LISEZMOI.format(outil=OUTIL_OFFICIEL).encode()
    files = [
        (annee.fec_nom, payload),
        (annee.fec_nom.replace(".txt", "_description.txt"), description),
        ("efi.txt", efi_txt),
        ("liasse.pdf", liasse_pdf),
        ("2042-c-pro.pdf", pro_pdf),
        ("suivi-39c.pdf", suivi_pdf),
        ("traces.json", _json(traces)),
        ("LISEZMOI.txt", readme),
    ]
    archive, sha, empreintes = zipper(files)
    return {
        "efi": sheet,
        "traces": traces,
        "suivi": suivi,
        "fec": {
            "nom": annee.fec_nom,
            "valide": controle["valide"],
            "bloquantes": controle["bloquantes"],
            "avertissements": controle["avertissements"],
            "outil_officiel": controle["outil_officiel"],
        },
        "empreintes": empreintes,
        "archive_nom": f"{resultat.dossier.siren}-sorties-{annee.annee}.zip",
        "archive_sha256": sha,
        "archive": archive,
    }


def ecrire(resultat: Resultat, dossier: Path) -> tuple[Path, dict[str, object]]:
    produit = produire(resultat)
    cible = dossier / "sorties"
    cible.mkdir(parents=True, exist_ok=True)
    archive = cible / str(produit["archive_nom"])
    contenu = produit["archive"]
    if not isinstance(contenu, bytes):
        raise TypeError("Archive illisible.")
    archive.write_bytes(contenu)
    return archive, produit


def pour_api(produit: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in produit.items() if key != "archive"}


def _annee_liasse(resultat: Resultat) -> Annee:
    for item in resultat.annees:
        if item.liasse:
            return item
    return resultat.annees[-1]


def _exercice(resultat: Resultat, annee: Annee):
    for exercice in resultat.dossier.exercices:
        if exercice.fin.year == annee.annee:
            return exercice
    raise KeyError(annee.annee)


def _lignes_pdf(sheet: dict[str, object], *, hors: str = "", seulement: str = "") -> list[str]:
    lines = ["Document de travail. Pas de teletransmission."]
    for row in _dicts(sheet["lignes"]):
        ecran = str(row["ecran"])
        if seulement and ecran != seulement:
            continue
        if hors and ecran == hors:
            continue
        lines.append(f"{ecran} {row['case']} {row['montant']}")
    for item in _dicts(sheet["controles"]):
        lines.append(str(item["texte"]))
    return lines


def _dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise TypeError("Feuille illisible.")
    return [item for item in value if isinstance(item, dict)]


def _json(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode()
