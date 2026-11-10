"""Trois états. L'outil calcule, l'utilisateur signe."""

from __future__ import annotations

from dataclasses import dataclass

from lmnp_core.dossier import Dossier

LIBELLES = {
    "brouillon": "Brouillon",
    "verifie": "Vérifié par l'utilisateur",
    "declare": "Déclaré",
}
PHRASE = "L'outil calcule, l'utilisateur signe."


@dataclass(frozen=True)
class Etat:
    demande: str
    effectif: str
    libelle: str
    registre_charge: bool
    fige_ecart: bool
    texte: str


def resoudre(dossier: Dossier, *, registre_charge: bool, empreinte: str) -> Etat:
    """Brouillon par défaut. Vérifié et Déclaré exigent leurs conditions, sinon on redescend."""
    demande = dossier.statut
    effectif = "brouillon"
    ecart = False
    if (
        demande in {"verifie", "declare"}
        and dossier.relu_notice
        and registre_charge
    ):
        effectif = "verifie"
    if demande == "declare" and effectif == "verifie":
        if dossier.date_depot and dossier.numero_accuse:
            if dossier.empreinte_figee and dossier.empreinte_figee != empreinte:
                ecart = True
                effectif = "brouillon"
            else:
                effectif = "declare"
        else:
            effectif = "verifie" if dossier.relu_notice and registre_charge else "brouillon"
    texte = PHRASE
    if not registre_charge and demande != "brouillon":
        texte = "Registre de cases absent pour ce millésime. L'état reste Brouillon."
    elif demande == "verifie" and not dossier.relu_notice:
        texte = "La case de relecture de la notice n'est pas cochée. L'état reste Brouillon."
    elif ecart:
        texte = "L'empreinte figée ne retrouve pas le calcul. L'état revient à Brouillon."
    return Etat(demande, effectif, LIBELLES[effectif], registre_charge, ecart, texte)
