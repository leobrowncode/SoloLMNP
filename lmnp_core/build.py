"""Orchestration : dossier, écritures, fiscal, cases, FEC."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lmnp_core.depreciation import dotation
from lmnp_core.dossier import Dossier, load_dossier
from lmnp_core.fec_out import render_fec
from lmnp_core.liasse_out import calculer_fiscal, cases_de, registre_charge
from lmnp_core.posting import Ecriture, _affecter, poster, soldes
from lmnp_core.status import Etat, resoudre


@dataclass
class Annee:
    annee: int
    liasse: bool
    produits: int
    autres_charges: int
    dotation: int
    plafond: int
    dotation_deductible: int
    amortissement_anterieur_utilise: int
    deficit_anterieur_utilise: int
    non_deduit: int
    resultat_comptable: int
    resultat_fiscal_avant_deficits: int
    resultat_fiscal: int
    deficit_cree: int
    banque: int
    emprunt_fin: int
    actif_net: int
    passif: int
    compte_108_fin: int
    compte_108_apres_affectation: int
    ouverture_213: int
    ouverture_281300: int
    ouverture_108: int
    stock_39c_fin: int
    stock_deficit_fin: int
    composants: dict[str, int]
    cases: dict[str, int]
    ecritures: list[Ecriture] = field(repr=False)
    fec_sha256: str = ""
    fec_nom: str = ""
    fec_texte: str = ""
    fec_description: str = ""
    fec_valide: bool = False

    def public(self) -> dict[str, Any]:
        return {
            "liasse": self.liasse,
            "produits": self.produits,
            "autres_charges": self.autres_charges,
            "dotation": self.dotation,
            "plafond": self.plafond,
            "dotation_deductible": self.dotation_deductible,
            "amortissement_anterieur_utilise": self.amortissement_anterieur_utilise,
            "deficit_anterieur_utilise": self.deficit_anterieur_utilise,
            "non_deduit": self.non_deduit,
            "resultat_comptable": self.resultat_comptable,
            "resultat_fiscal_avant_deficits": self.resultat_fiscal_avant_deficits,
            "resultat_fiscal": self.resultat_fiscal,
            "deficit_cree": self.deficit_cree,
            "banque": self.banque,
            "emprunt_fin": self.emprunt_fin,
            "actif_net": self.actif_net,
            "passif": self.passif,
            "compte_108_fin": self.compte_108_fin,
            "compte_108_apres_affectation": self.compte_108_apres_affectation,
            "ouverture_213": self.ouverture_213,
            "ouverture_281300": self.ouverture_281300,
            "ouverture_108": self.ouverture_108,
            "stock_39c_fin": self.stock_39c_fin,
            "stock_deficit_fin": self.stock_deficit_fin,
            "composants": self.composants,
            "cases": self.cases,
        }


@dataclass
class Resultat:
    dossier: Dossier
    annees: list[Annee]
    etat: Etat
    empreinte: str

    def annee(self, year: int) -> Annee:
        for item in self.annees:
            if item.annee == year:
                return item
        raise KeyError(year)

    def to_json(self) -> dict[str, Any]:
        return {
            "nom": self.dossier.nom,
            "siret": self.dossier.siret,
            "millesime": self.dossier.millesime,
            "etat": {
                "demande": self.etat.demande,
                "effectif": self.etat.effectif,
                "libelle": self.etat.libelle,
                "registre_charge": self.etat.registre_charge,
                "fige_ecart": self.etat.fige_ecart,
                "texte": self.etat.texte,
            },
            "empreinte": self.empreinte,
            "annees": {
                str(item.annee): item.public() | {"fec_sha256": item.fec_sha256}
                for item in self.annees
            },
        }


def build_path(path: Path) -> Resultat:
    return build_dossier(load_dossier(path))


def build_dossier(dossier: Dossier) -> Resultat:
    series = poster(dossier)
    amortissements: list[Any] = []
    deficits: list[Any] = []
    cumul: dict[str, int] = {plan.cle: 0 for plan in dossier.plans}
    annees: list[Annee] = []
    for index, (exercice, entries) in enumerate(zip(dossier.exercices, series, strict=True)):
        produits, charges, autres, dotation_annee = _flux(entries)
        split, amortissements, deficits_apres = calculer_fiscal(
            annee=exercice.fin.year,
            produits=produits,
            autres_charges=autres,
            dotation_annee=dotation_annee,
            amortissements=amortissements,
            deficits=deficits,
        )
        composants = {
            plan.cle: dotation(plan, exercice.debut, exercice.fin) for plan in dossier.plans
        }
        liasse = str(exercice.fin.year) == dossier.millesime
        built = (
            cases_de(
                dossier,
                index,
                entries,
                produits=produits,
                charges=charges,
                dotation_annee=dotation_annee,
                split=split,
                plans=dossier.plans,
                dotations_anterieures=dict(cumul),
                deficits=list(deficits),
            )
            if liasse
            else {}
        )
        nets = soldes(entries)
        folded = _affecter(nets)
        actif = sum(net for compte, net in nets.items() if compte.startswith(("2", "5")))
        capitaux = -sum(net for compte, net in nets.items() if compte.startswith("1"))
        passif = capitaux + split.accounting_result
        fec = render_fec(
            entries, siren=dossier.siren, debut=exercice.debut, fin=exercice.fin
        )
        validation = fec["validation"]
        if not isinstance(validation, dict):
            raise RuntimeError("Validation FEC illisible.")
        annees.append(
            Annee(
                annee=exercice.fin.year,
                liasse=liasse,
                produits=produits,
                autres_charges=autres,
                dotation=dotation_annee,
                plafond=split.capacity,
                dotation_deductible=split.current_deductible,
                amortissement_anterieur_utilise=split.prior_depreciation_used,
                deficit_anterieur_utilise=split.prior_tax_loss_used,
                non_deduit=split.unused_depreciation,
                resultat_comptable=split.accounting_result,
                resultat_fiscal_avant_deficits=split.fiscal_before_losses,
                resultat_fiscal=split.fiscal_result,
                deficit_cree=max(0, -split.fiscal_before_losses),
                banque=nets.get("512000", 0),
                emprunt_fin=-nets.get("164000", 0),
                actif_net=actif,
                passif=passif,
                compte_108_fin=-nets.get("108000", 0),
                compte_108_apres_affectation=-folded.get("108000", 0),
                ouverture_213=_cote(entries, "213000", "debit"),
                ouverture_281300=_cote(entries, "281300", "credit"),
                ouverture_108=_cote(entries, "108000", "credit"),
                stock_39c_fin=sum(stock.remaining_before() for stock in amortissements),
                stock_deficit_fin=sum(stock.remaining_before() for stock in deficits_apres),
                composants=composants,
                cases=built,
                ecritures=entries,
                fec_sha256=str(fec["sha256"]),
                fec_nom=str(fec["filename"]),
                fec_texte=bytes(fec["content"]).decode("utf-8"),  # type: ignore[arg-type]
                fec_description=str(fec["description"]),
                fec_valide=bool(validation["valid"]),
            )
        )
        for plan in dossier.plans:
            cumul[plan.cle] = cumul.get(plan.cle, 0) + composants[plan.cle]
        deficits = deficits_apres
    empreinte = _empreinte(annees)
    etat = resoudre(
        dossier, registre_charge=registre_charge(dossier.millesime), empreinte=empreinte
    )
    return Resultat(dossier, annees, etat, empreinte)


def _flux(entries: list[Ecriture]) -> tuple[int, dict[str, int], int, int]:
    produits = 0
    charges: dict[str, int] = {}
    for entry in entries:
        for line in entry.lignes:
            if line.compte.startswith("7"):
                produits += line.credit - line.debit
            elif line.compte.startswith("6"):
                charges[line.compte] = charges.get(line.compte, 0) + line.debit - line.credit
    dotation_annee = sum(montant for compte, montant in charges.items() if compte.startswith("681"))
    autres = sum(charges.values()) - dotation_annee
    return produits, charges, autres, dotation_annee


def _cote(entries: list[Ecriture], compte: str, side: str) -> int:
    total = 0
    for entry in entries:
        if entry.journal != "AN":
            continue
        for line in entry.lignes:
            if line.compte == compte:
                total += line.debit if side == "debit" else line.credit
    return total


def _empreinte(annees: list[Annee]) -> str:
    payload = json.dumps([item.public() for item in annees], sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
