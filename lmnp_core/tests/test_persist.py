from pathlib import Path

import pytest

from lmnp_core.dossier import DossierError
from lmnp_core.persist import creer_dossier, enregistrer, lire_chemin, lister_modeles
from lmnp_core.siret import valide

GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "premier-exercice" / "input"


def test_siret_luhn() -> None:
    assert valide("12345678900015")
    assert not valide("12345678900017")


def test_lister_modeles() -> None:
    modeles = lister_modeles()
    assert any(item["id"] == "premier-exercice" for item in modeles)


def test_lire_et_grille() -> None:
    payload = lire_chemin(GOLDEN)
    assert payload["dossier"]["regime"] == "lmnp"
    assert len(payload["grille"]) >= 6
    assert len(payload["mouvements"]) > 0


def test_enregistrer_dans_temporaire(tmp_path: Path) -> None:
    payload = lire_chemin(GOLDEN)
    mapping = dict(payload["dossier"])
    mapping["nom"] = "Essai persistance"
    enregistrer(tmp_path, mapping, payload["mouvements"])
    relu = lire_chemin(tmp_path)
    assert relu["dossier"]["nom"] == "Essai persistance"


def test_creer_dossier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lmnp_core import persist

    monkeypatch.setattr(persist, "DATA_ROOT", tmp_path)
    created = creer_dossier("premier-exercice", "copie-test")
    assert Path(created["chemin"]).is_dir()
    with pytest.raises(DossierError):
        creer_dossier("inconnu", "x")
