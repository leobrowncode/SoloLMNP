"""Propriétés : équilibre, actif = passif, amortissement jamais créateur de déficit."""

import random

from lmnp_core.build import build_dossier
from lmnp_core.dossier import dossier_from_mapping
from lmnp_core.posting import poster


def test_random_dossiers_stay_balanced() -> None:
    rng = random.Random(2025)
    for _ in range(40):
        dossier = dossier_from_mapping(_payload(rng))
        for year in poster(dossier):
            for entry in year:
                assert entry.equilibre()
            nets = {}
            for entry in year:
                for line in entry.lignes:
                    nets[line.compte] = nets.get(line.compte, 0) + line.debit - line.credit
            assert sum(nets.values()) == 0
        result = build_dossier(dossier)
        for item in result.annees:
            assert item.actif_net == item.passif
            assert item.deficit_cree <= max(0, item.autres_charges - item.produits)


def _payload(rng: random.Random) -> dict[str, object]:
    base = rng.randint(50, 4000) * 1000
    life = rng.choice([120, 180, 240, 360])
    rent = rng.randint(0, 800) * 100
    charge = rng.randint(0, 900) * 100
    mouvements: list[dict[str, object]] = []
    if rent:
        mouvements.append(
            {
                "date": "2025-06-15",
                "piece": "LOY",
                "libelle": "Loyer",
                "compte": "706000",
                "debit_centimes": 0,
                "credit_centimes": rent,
            }
        )
    if charge:
        mouvements.append(
            {
                "date": "2025-09-30",
                "piece": "CHG",
                "libelle": "Charges",
                "compte": "614000",
                "debit_centimes": charge,
                "credit_centimes": 0,
            }
        )
    return {
        "nom": "Alea",
        "siret": "12345678900017",
        "debut_activite": "2025-01-01",
        "millesime": "2025",
        "regime": "lmnp",
        "bien": {
            "nom": "Studio",
            "date_mise_en_service": "2025-01-01",
            "terrain_centimes": 0,
            "batiment_centimes": base,
            "ventilation": "unique",
            "duree_mois": life,
        },
        "apport_centimes": base + charge + 1,
        "exercices": [
            {
                "debut": "2025-01-01",
                "fin": "2025-12-31",
                "mouvements": mouvements,
            }
        ],
    }
