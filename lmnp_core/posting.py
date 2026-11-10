"""Écritures dérivées du dossier. Partie double, centimes, jamais éditées à la main."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from lmnp_core.depreciation import Plan, dotation
from lmnp_core.dossier import Dossier, DossierError, Exercice, Mouvement

JOURNALS = {
    "AN": "A-nouveaux",
    "OD": "Operations diverses",
    "BQ": "Banque",
    "AC": "Achats",
    "VE": "Ventes",
}


@dataclass(frozen=True)
class Ligne:
    compte: str
    libelle: str
    debit: int
    credit: int


@dataclass(frozen=True)
class Ecriture:
    numero: int
    journal: str
    date: date
    piece: str
    libelle: str
    lignes: tuple[Ligne, ...]

    def equilibre(self) -> bool:
        return sum(line.debit for line in self.lignes) == sum(line.credit for line in self.lignes)


@dataclass
class _Draft:
    phase: int
    date: date
    ordre: int
    journal: str
    piece: str
    libelle: str
    lignes: list[Ligne]


def poster(dossier: Dossier) -> list[list[Ecriture]]:
    """Une liste d'écritures par exercice, dans l'ordre du dossier."""
    reporte: dict[str, int] = {}
    years: list[list[Ecriture]] = []
    acquisition_faite = False
    apport_fait = False
    emprunt_fait = False
    for index, exercice in enumerate(dossier.exercices):
        drafts: list[_Draft] = []
        if reporte:
            drafts.append(_anouveaux(exercice.debut, reporte))
        if not apport_fait and dossier.apport and _dans(dossier.debut_activite, exercice):
            drafts.append(_apport(dossier, exercice))
            apport_fait = True
        if (
            not emprunt_fait
            and dossier.emprunt_capital
            and dossier.emprunt_date is not None
            and _dans(dossier.emprunt_date, exercice)
        ):
            drafts.append(_emprunt(dossier))
            emprunt_fait = True
        if not acquisition_faite and _dans(dossier.plans[0].mise_en_service, exercice):
            drafts.append(_acquisition(dossier, exercice))
            acquisition_faite = True
        for ordre, mouvement in enumerate(exercice.mouvements):
            if not _dans(mouvement.date, exercice):
                raise DossierError(
                    f"Le mouvement {mouvement.piece} est hors de l'exercice {exercice.debut}."
                )
            drafts.append(_mouvement(mouvement, ordre))
        for plan in dossier.plans:
            amount = dotation(plan, exercice.debut, exercice.fin)
            if amount > 0:
                drafts.append(_dotation(plan, exercice.fin, amount))
        drafts.sort(key=lambda item: (item.date, item.phase, item.ordre))
        entries = [
            Ecriture(numero, item.journal, item.date, item.piece, item.libelle, tuple(item.lignes))
            for numero, item in enumerate(drafts, start=1)
        ]
        for entry in entries:
            if not entry.equilibre() or not entry.lignes:
                raise DossierError(f"Écriture {entry.numero} déséquilibrée.")
        nets = soldes(entries)
        if sum(nets.values()) != 0:
            raise DossierError(f"Exercice {index + 1} : débit et crédit ne s'égalisent pas.")
        reporte = _affecter(nets)
        years.append(entries)
    if not acquisition_faite:
        raise DossierError("La mise en service n'est dans aucun exercice.")
    return years


def soldes(entries: list[Ecriture]) -> dict[str, int]:
    """Soldes débit moins crédit."""
    nets: dict[str, int] = {}
    for entry in entries:
        for line in entry.lignes:
            nets[line.compte] = nets.get(line.compte, 0) + line.debit - line.credit
    return {compte: net for compte, net in nets.items() if net}


def _affecter(nets: dict[str, int]) -> dict[str, int]:
    """Bilan d'ouverture suivant : résultat viré au compte 108, classes 6 et 7 soldées."""
    result_debit = sum(net for compte, net in nets.items() if compte[0] in {"6", "7"})
    suivant = {compte: net for compte, net in nets.items() if compte[0] not in {"6", "7"}}
    suivant["108000"] = suivant.get("108000", 0) + result_debit
    return {compte: net for compte, net in suivant.items() if net}


def _anouveaux(jour: date, nets: dict[str, int]) -> _Draft:
    lignes: list[Ligne] = []
    for compte in sorted(nets):
        net = nets[compte]
        if net > 0:
            lignes.append(Ligne(compte, "A-nouveaux", net, 0))
        elif net < 0:
            lignes.append(Ligne(compte, "A-nouveaux", 0, -net))
    return _Draft(0, jour, 0, "AN", "AN", "A-nouveaux", lignes)


def _apport(dossier: Dossier, exercice: Exercice) -> _Draft:
    jour = dossier.debut_activite
    return _Draft(
        1,
        jour,
        0,
        "OD",
        "APPORT",
        "Apport de l'exploitant",
        [
            Ligne("512000", "Apport de l'exploitant", dossier.apport, 0),
            Ligne("108000", "Apport de l'exploitant", 0, dossier.apport),
        ],
    )


def _emprunt(dossier: Dossier) -> _Draft:
    if dossier.emprunt_date is None:
        raise DossierError("Date d'emprunt manquante.")
    libelle = "Debloquage de l'emprunt"
    return _Draft(
        2,
        dossier.emprunt_date,
        0,
        "BQ",
        "DEBLOCAGE",
        libelle,
        [
            Ligne("512000", libelle, dossier.emprunt_capital, 0),
            Ligne("164000", libelle, 0, dossier.emprunt_capital),
        ],
    )


def _acquisition(dossier: Dossier, exercice: Exercice) -> _Draft:
    jour = dossier.plans[0].mise_en_service
    lignes: list[Ligne] = []
    total = 0
    if dossier.terrain:
        lignes.append(Ligne("211000", "Terrain", dossier.terrain, 0))
        total += dossier.terrain
    for plan in dossier.plans:
        lignes.append(Ligne(plan.compte, plan.libelle, plan.base, 0))
        total += plan.base
    lignes.append(Ligne("512000", "Acquisition du bien", 0, total))
    return _Draft(3, jour, 0, "OD", "ACQ", "Acquisition du bien", lignes)


def _mouvement(mouvement: Mouvement, ordre: int) -> _Draft:
    journal = "VE" if mouvement.compte.startswith("7") else "AC"
    if mouvement.compte.startswith("5") or mouvement.compte.startswith("16"):
        journal = "BQ"
    elif mouvement.compte.startswith("1"):
        journal = "OD"
    libelle = mouvement.libelle
    lignes = [Ligne(mouvement.compte, libelle, mouvement.debit, mouvement.credit)]
    if mouvement.debit:
        lignes.append(Ligne("512000", libelle, 0, mouvement.debit))
    else:
        lignes.append(Ligne("512000", libelle, mouvement.credit, 0))
    return _Draft(4, mouvement.date, ordre, journal, mouvement.piece, libelle, lignes)


def _dotation(plan: Plan, jour: date, amount: int) -> _Draft:
    libelle = f"Dotation {plan.libelle}"
    return _Draft(
        5,
        jour,
        0,
        "OD",
        f"DOT-{plan.cle}",
        libelle,
        [
            Ligne("681100", libelle, amount, 0),
            Ligne(plan.compte_amortissement, libelle, 0, amount),
        ],
    )


def _dans(jour: date, exercice: Exercice) -> bool:
    return exercice.debut <= jour <= exercice.fin
