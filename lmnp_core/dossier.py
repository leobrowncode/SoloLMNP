"""Chargement d'un dossier v1 (YAML + CSV). Refus du hors spec."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from lmnp_core.depreciation import COMPOSANTS_DEFAUT, Plan, shares
from lmnp_core.yamlio import loads

BANNED_PREFIXES = ("445", "675", "775")


class DossierError(ValueError):
    """Le dossier n'est pas calculable en v1."""


@dataclass(frozen=True)
class Mouvement:
    date: date
    piece: str
    libelle: str
    compte: str
    debit: int
    credit: int


@dataclass(frozen=True)
class Exercice:
    debut: date
    fin: date
    mouvements: tuple[Mouvement, ...]


@dataclass(frozen=True)
class Dossier:
    nom: str
    siret: str
    debut_activite: date
    millesime: str
    regime: str
    statut: str
    relu_notice: bool
    date_depot: date | None
    numero_accuse: str | None
    empreinte_figee: str | None
    plans: tuple[Plan, ...]
    terrain: int
    emprunt_capital: int
    emprunt_date: date | None
    apport: int
    exercices: tuple[Exercice, ...]
    source: Path | None = None

    @property
    def siren(self) -> str:
        return self.siret[:9]


def load_dossier(path: Path) -> Dossier:
    folder = path if path.is_dir() else path.parent
    document = path / "dossier.yaml" if path.is_dir() else path
    if not document.is_file():
        raise DossierError(f"dossier.yaml introuvable dans {path}.")
    raw = loads(document.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise DossierError("dossier.yaml doit être une map.")
    return _dossier(raw, folder)


def dossier_from_mapping(raw: dict[str, object], folder: Path | None = None) -> Dossier:
    return _dossier(raw, folder or Path())


def _dossier(raw: dict[str, object], folder: Path) -> Dossier:
    regime = str(_need(raw, "regime"))
    if regime != "lmnp":
        raise DossierError("Seul le LMNP à l'impôt sur le revenu est dans la v1.")
    millesime = str(_need(raw, "millesime"))
    if millesime == "2027":
        raise DossierError("Le millésime 2027 est hors v1.")
    if len(millesime) != 4 or not millesime.isdigit():
        raise DossierError("Le millésime est une année sur quatre chiffres.")
    siret = str(_need(raw, "siret"))
    if len(siret) != 14 or not siret.isdigit():
        raise DossierError("Le SIRET fait 14 chiffres.")
    statut = str(raw.get("statut") or "brouillon")
    if statut not in {"brouillon", "verifie", "declare"}:
        raise DossierError("Statut : brouillon, verifie ou declare.")
    bien = raw.get("bien")
    if not isinstance(bien, dict):
        raise DossierError("Le bien manque.")
    plans, terrain = _plans(bien)
    emprunt = raw.get("emprunt")
    capital = 0
    emprunt_date: date | None = None
    if isinstance(emprunt, dict):
        capital = _int(emprunt.get("capital_centimes"), "capital d'emprunt")
        emprunt_date = _date(str(_need(emprunt, "date")), "date d'emprunt")
    exercices_raw = raw.get("exercices")
    if not isinstance(exercices_raw, list) or not exercices_raw:
        raise DossierError("Au moins un exercice est requis.")
    exercices = tuple(_exercice(item, folder) for item in exercices_raw)
    depot = raw.get("date_depot")
    accuse = raw.get("numero_accuse")
    figee = raw.get("empreinte_figee")
    return Dossier(
        nom=str(_need(raw, "nom")),
        siret=siret,
        debut_activite=_date(str(_need(raw, "debut_activite")), "début d'activité"),
        millesime=millesime,
        regime=regime,
        statut=statut,
        relu_notice=bool(raw.get("relu_notice")),
        date_depot=_date(str(depot), "date de dépôt") if depot else None,
        numero_accuse=str(accuse) if accuse else None,
        empreinte_figee=str(figee) if figee else None,
        plans=plans,
        terrain=terrain,
        emprunt_capital=capital,
        emprunt_date=emprunt_date,
        apport=_int(raw.get("apport_centimes"), "apport"),
        exercices=exercices,
        source=folder,
    )


def _plans(bien: dict[str, object]) -> tuple[tuple[Plan, ...], int]:
    service = _date(str(_need(bien, "date_mise_en_service")), "mise en service")
    terrain = _int(bien.get("terrain_centimes"), "terrain")
    batiment = _int(bien.get("batiment_centimes"), "bâtiment")
    frais = _int(bien.get("frais_centimes") or 0, "frais")
    mobilier = _int(bien.get("mobilier_centimes") or 0, "mobilier")
    base = batiment + frais
    if base < 0 or terrain < 0 or mobilier < 0:
        raise DossierError("Les valeurs du bien sont des centimes positifs.")
    ventilation = str(bien.get("ventilation") or "composants")
    plans: list[Plan] = []
    if ventilation == "composants":
        if base <= 0:
            raise DossierError("La ventilation par composants exige un bâtiment.")
        for (cle, libelle, _ratio, duree, compte, amort), part in zip(
            COMPOSANTS_DEFAUT, shares(base), strict=True
        ):
            if part <= 0:
                continue
            plans.append(Plan(cle, libelle, part, duree, compte, amort, service))
    elif ventilation == "unique":
        if base <= 0:
            raise DossierError("Le bâtiment manque.")
        duree = _int(bien.get("duree_mois"), "durée")
        compte = str(bien.get("compte_immobilisation") or "213000")
        amort = str(bien.get("compte_amortissement") or "281300")
        plans.append(Plan("construction", "Construction", base, duree, compte, amort, service))
    else:
        raise DossierError("Ventilation : composants ou unique.")
    if mobilier:
        life = _int(bien.get("mobilier_duree_mois"), "durée du mobilier")
        plans.append(
            Plan("mobilier", "Mobilier", mobilier, life, "218400", "281840", service)
        )
    for plan in plans:
        _guard_account(plan.compte)
        _guard_account(plan.compte_amortissement)
    return tuple(plans), terrain


def _exercice(item: object, folder: Path) -> Exercice:
    if not isinstance(item, dict):
        raise DossierError("Exercice illisible.")
    debut = _date(str(_need(item, "debut")), "début d'exercice")
    fin = _date(str(_need(item, "fin")), "fin d'exercice")
    if debut > fin:
        raise DossierError("L'exercice se termine avant de commencer.")
    name = item.get("mouvements")
    mouvements: tuple[Mouvement, ...] = ()
    if isinstance(name, str):
        mouvements = _csv(folder / name)
    elif isinstance(name, list):
        mouvements = tuple(_mouvement(row) for row in name)
    return Exercice(debut, fin, mouvements)


def _csv(path: Path) -> tuple[Mouvement, ...]:
    if not path.is_file():
        raise DossierError(f"CSV introuvable : {path.name}.")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return tuple(_mouvement(row) for row in rows)


def _mouvement(row: object) -> Mouvement:
    if not isinstance(row, dict):
        raise DossierError("Ligne de mouvement illisible.")
    compte = str(row.get("compte") or "")
    _guard_account(compte)
    debit = _int(row.get("debit_centimes"), "débit")
    credit = _int(row.get("credit_centimes"), "crédit")
    if (debit > 0) == (credit > 0):
        raise DossierError(f"La ligne {row.get('piece')} a un seul sens, débit ou crédit.")
    return Mouvement(
        date=_date(str(row.get("date")), "date de mouvement"),
        piece=str(row.get("piece") or ""),
        libelle=str(row.get("libelle") or ""),
        compte=compte,
        debit=debit,
        credit=credit,
    )


def _guard_account(compte: str) -> None:
    if compte.startswith(BANNED_PREFIXES):
        raise DossierError(
            f"Le compte {compte} relève de la TVA ou d'une cession, hors v1."
        )


def _need(raw: dict[str, object], key: str) -> object:
    if key not in raw or raw[key] in (None, ""):
        raise DossierError(f"Champ requis : {key}.")
    return raw[key]


def _int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        if isinstance(value, str) and value.lstrip("-").isdigit():
            return int(value)
        raise DossierError(f"{label} : centimes entiers requis.")
    return value


def _date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise DossierError(f"{label} : date AAAA-MM-JJ.") from exc
