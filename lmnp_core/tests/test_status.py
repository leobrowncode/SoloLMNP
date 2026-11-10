from dataclasses import replace
from pathlib import Path

from lmnp_core.build import build_path
from lmnp_core.status import resoudre

GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "plafond-39c" / "input"


def test_three_states() -> None:
    built = build_path(GOLDEN)
    dossier = built.dossier
    assert built.etat.effectif == "brouillon"
    assert "signe" in built.etat.texte

    verified = resoudre(
        replace(dossier, statut="verifie", relu_notice=False),
        registre_charge=True,
        empreinte=built.empreinte,
    )
    assert verified.effectif == "brouillon"

    checked = resoudre(
        replace(dossier, statut="verifie", relu_notice=True),
        registre_charge=True,
        empreinte=built.empreinte,
    )
    assert checked.effectif == "verifie"
    assert checked.libelle == "Vérifié par l'utilisateur"

    missing_registry = resoudre(
        replace(dossier, statut="verifie", relu_notice=True),
        registre_charge=False,
        empreinte=built.empreinte,
    )
    assert missing_registry.effectif == "brouillon"

    declared = resoudre(
        replace(
            dossier,
            statut="declare",
            relu_notice=True,
            date_depot=dossier.debut_activite,
            numero_accuse="ACC-1",
        ),
        registre_charge=True,
        empreinte=built.empreinte,
    )
    assert declared.effectif == "declare"
    assert declared.libelle == "Déclaré"

    drifted = resoudre(
        replace(
            dossier,
            statut="declare",
            relu_notice=True,
            date_depot=dossier.debut_activite,
            numero_accuse="ACC-1",
            empreinte_figee="0" * 64,
        ),
        registre_charge=True,
        empreinte=built.empreinte,
    )
    assert drifted.effectif == "brouillon"
    assert drifted.fige_ecart
