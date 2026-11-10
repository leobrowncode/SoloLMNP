"""Persistance locale YAML + CSV pour la saisie v1."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

from lmnp_core.depreciation import COMPOSANTS_DEFAUT, shares
from lmnp_core.dossier import DossierError, dossier_from_mapping, load_dossier
from lmnp_core.yamlio import loads

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "golden"
DATA_ROOT = ROOT / "data" / "v1-dossiers"


def lister_modeles() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not GOLDEN.is_dir():
        return items
    for child in sorted(GOLDEN.iterdir()):
        dossier = child / "input" / "dossier.yaml"
        if dossier.is_file():
            items.append(
                {
                    "id": child.name,
                    "chemin": str((child / "input").resolve()),
                    "etiquette": child.name.replace("-", " ").capitalize(),
                }
            )
    return items


def lire_chemin(chemin: Path) -> dict[str, Any]:
    load_dossier(chemin)
    raw = _lire_yaml(chemin)
    mouvements = _lire_mouvements(chemin, raw)
    return {
        "chemin": str(chemin.resolve()),
        "dossier": raw,
        "mouvements": mouvements,
        "grille": grille_apercu(raw),
    }


def enregistrer(
    chemin: Path,
    mapping: dict[str, Any],
    mouvements: list[dict[str, Any]] | None,
) -> dict[str, str]:
    folder = chemin if chemin.is_dir() else chemin.parent
    folder.mkdir(parents=True, exist_ok=True)
    if mouvements is not None:
        exercices = mapping.get("exercices")
        if isinstance(exercices, list) and exercices:
            nom = str(exercices[0].get("mouvements") or "mouvements.csv")
            _ecrire_csv(folder / nom, mouvements)
    cible = folder / "dossier.yaml"
    cible.write_text(_dumps(mapping), encoding="utf-8")
    dossier_from_mapping(mapping, folder)
    return {"chemin": str(folder.resolve())}


def creer_dossier(cle_modele: str, nom_dossier: str) -> dict[str, str]:
    source = GOLDEN / cle_modele / "input"
    if not (source / "dossier.yaml").is_file():
        raise DossierError(f"Modèle inconnu : {cle_modele}.")
    cible = DATA_ROOT / nom_dossier
    if cible.exists():
        raise DossierError("Ce nom de dossier existe déjà.")
    shutil.copytree(source, cible)
    return {"chemin": str(cible.resolve())}


def assurer_data(chemin: str | None) -> Path:
    if chemin:
        path = Path(chemin).resolve()
        if not (path / "dossier.yaml").is_file() and path.is_file():
            path = path.parent
        if not (path / "dossier.yaml").is_file():
            raise DossierError("dossier.yaml introuvable.")
        return path
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    return DATA_ROOT


def grille_apercu(raw: dict[str, Any]) -> list[dict[str, Any]]:
    bien = raw.get("bien")
    if not isinstance(bien, dict):
        return []
    batiment = _entier(bien.get("batiment_centimes"), 0)
    frais = _entier(bien.get("frais_centimes"), 0)
    base = batiment + frais
    parts = shares(base) if base > 0 else [0] * len(COMPOSANTS_DEFAUT)
    lignes: list[dict[str, Any]] = []
    for (cle, libelle, ratio, duree, compte, amort), part in zip(
        COMPOSANTS_DEFAUT, parts, strict=True
    ):
        lignes.append(
            {
                "cle": cle,
                "libelle": libelle,
                "ratio_dix_millieme": ratio,
                "duree_mois": duree,
                "compte": compte,
                "compte_amortissement": amort,
                "base_centimes": part,
            }
        )
    mobilier = _entier(bien.get("mobilier_centimes"), 0)
    if mobilier:
        lignes.append(
            {
                "cle": "mobilier",
                "libelle": "Mobilier",
                "ratio_dix_millieme": None,
                "duree_mois": _entier(bien.get("mobilier_duree_mois"), 84),
                "compte": "218400",
                "compte_amortissement": "281840",
                "base_centimes": mobilier,
            }
        )
    return lignes


def categories_annee() -> list[dict[str, str]]:
    return [
        {"id": "loyer", "libelle": "Loyers", "compte": "706000", "sens": "credit"},
        {"id": "charges", "libelle": "Charges de copropriété", "compte": "614000", "sens": "debit"},
        {"id": "taxe", "libelle": "Taxe foncière", "compte": "635000", "sens": "debit"},
        {"id": "assurance", "libelle": "Assurance", "compte": "616000", "sens": "debit"},
        {"id": "gestion", "libelle": "Frais de gestion", "compte": "622000", "sens": "debit"},
        {"id": "cfe", "libelle": "CFE", "compte": "635000", "sens": "debit"},
        {"id": "travaux", "libelle": "Travaux", "compte": "615000", "sens": "debit"},
        {"id": "interets", "libelle": "Intérêts d'emprunt", "compte": "661000", "sens": "debit"},
        {"id": "capital", "libelle": "Capital emprunt", "compte": "164000", "sens": "debit"},
        {
            "id": "assurance_emprunt",
            "libelle": "Assurance emprunteur",
            "compte": "616000",
            "sens": "debit",
        },
    ]


def _lire_yaml(chemin: Path) -> dict[str, Any]:
    document = chemin / "dossier.yaml" if chemin.is_dir() else chemin
    raw = loads(document.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise DossierError("dossier.yaml illisible.")
    return raw


def _lire_mouvements(chemin: Path, raw: dict[str, Any]) -> list[dict[str, Any]]:
    exercices = raw.get("exercices")
    if not isinstance(exercices, list) or not exercices:
        return []
    premier = exercices[0]
    if not isinstance(premier, dict):
        return []
    nom = premier.get("mouvements")
    if isinstance(nom, list):
        return [dict(item) for item in nom if isinstance(item, dict)]
    if not isinstance(nom, str):
        return []
    path = (chemin if chemin.is_dir() else chemin.parent) / nom
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _ecrire_csv(path: Path, lignes: list[dict[str, Any]]) -> None:
    champs = ("date", "piece", "libelle", "compte", "debit_centimes", "credit_centimes")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=champs)
        writer.writeheader()
        for ligne in lignes:
            writer.writerow({key: ligne.get(key, "") for key in champs})


def _dumps(mapping: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    pad = "  " * indent
    for key, value in mapping.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.append(_dumps(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{pad}{key}:")
            for item in value:
                if isinstance(item, dict):
                    first = True
                    for sub_key, sub_value in item.items():
                        prefix = f"{pad}  - " if first else f"{pad}    "
                        first = False
                        rendered = _scalaire(sub_value)
                        lines.append(f"{prefix}{sub_key}: {rendered}")
                else:
                    lines.append(f"{pad}  - {_scalaire(item)}")
        else:
            lines.append(f"{pad}{key}: {_scalaire(value)}")
    return "\n".join(line for line in lines if line != "")


def _scalaire(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    text = str(value)
    if text.isdigit() and len(text) in {9, 14}:
        return f'"{text}"'
    if any(char in text for char in ":#") or not text:
        return json.dumps(text, ensure_ascii=False)
    return text


def _entier(value: object, default: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
    return default
