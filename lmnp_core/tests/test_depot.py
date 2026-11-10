"""Fichiers locaux et Blob (faux client) : même dossier, comptes séparés."""

from pathlib import Path

import pytest

from lmnp_core.depot import (
    AdaptateurBlob,
    DepotAbsent,
    DepotBlob,
    DepotError,
    DepotFichiers,
)
from lmnp_core.dossier import DossierError
from lmnp_core.persist import copier_modele, enregistrer_owner, lire_owner


class _FauxBlob:
    def __init__(self) -> None:
        self.objets: dict[str, bytes] = {}
        self.types: dict[str, str] = {}

    def put(self, pathname: str, content: bytes, content_type: str, *, overwrite: bool) -> None:
        del overwrite
        self.objets[pathname] = content
        self.types[pathname] = content_type

    def get(self, pathname: str) -> bytes:
        try:
            return self.objets[pathname]
        except KeyError as exc:
            raise FileNotFoundError(pathname) from exc

    def list_pathnames(self, prefix: str) -> list[str]:
        return sorted(nom for nom in self.objets if nom.startswith(prefix))

    def delete(self, pathname: str) -> None:
        self.objets.pop(pathname, None)


class _AbsentExotique(Exception):
    pass


class _ClientExotique:
    def get(self, pathname: str) -> bytes:
        raise _AbsentExotique(pathname)

    def put(self, pathname: str, content: bytes, content_type: str, *, overwrite: bool) -> None:
        del pathname, content, content_type, overwrite

    def list_pathnames(self, prefix: str) -> list[str]:
        del prefix
        return []


def test_fichiers_copient_le_modele_et_isolent(tmp_path: Path) -> None:
    depot = DepotFichiers(tmp_path)
    ada = copier_modele(depot, "ada", "premier-exercice")
    bea = copier_modele(depot, "bea", "plafond-39c")
    assert ada["dossier"]["nom"] == "Reference premier exercice"
    assert bea["dossier"]["nom"] != ada["dossier"]["nom"]
    ada["dossier"]["nom"] = "Dossier Ada"
    enregistre = enregistrer_owner(depot, "ada", ada["dossier"], ada["mouvements"])
    assert enregistre["dossier"]["nom"] == "Dossier Ada"
    assert lire_owner(depot, "bea")["dossier"]["nom"] != "Dossier Ada"
    assert (tmp_path / "ada" / "dossier.yaml").is_file()
    assert (tmp_path / "bea" / "dossier.yaml").is_file()


def test_blob_faux_client_memes_octets_et_prefixe() -> None:
    client = _FauxBlob()
    depot = DepotBlob(client)
    depot.ecrire("ada", "dossier.yaml", b"nom: Ada\n")
    depot.ecrire("ada", "justificatifs/quittance.pdf", b"%PDF")
    depot.ecrire("bea", "dossier.yaml", b"nom: Bea\n")
    assert depot.lire("ada", "dossier.yaml") == b"nom: Ada\n"
    assert client.objets["v1/ada/dossier.yaml"] == b"nom: Ada\n"
    assert client.types["v1/ada/justificatifs/quittance.pdf"] == "application/pdf"
    assert depot.lister("ada") == ["dossier.yaml", "justificatifs/quittance.pdf"]
    assert depot.lister("ada", "justificatifs") == ["justificatifs/quittance.pdf"]
    assert depot.lire("bea", "dossier.yaml") == b"nom: Bea\n"
    with pytest.raises(DepotAbsent):
        depot.lire("ada", "absent.txt")


def test_chemins_refusent_la_sortie_du_compte(tmp_path: Path) -> None:
    fichiers = DepotFichiers(tmp_path)
    blob = DepotBlob(_FauxBlob())
    for depot in (fichiers, blob):
        depot.ecrire("ada", "dossier.yaml", b"a")
        for relatif in ("../bea/dossier.yaml", "/etc/passwd", "justificatifs/../../x", "a\\b"):
            with pytest.raises(DepotError):
                depot.lire("ada", relatif)
            with pytest.raises(DepotError):
                depot.ecrire("ada", relatif, b"x")


def test_adaptateur_traduit_l_absence() -> None:
    adapte = AdaptateurBlob(_ClientExotique(), (_AbsentExotique,))
    with pytest.raises(FileNotFoundError):
        adapte.get("v1/ada/dossier.yaml")


def test_modele_inconnu(tmp_path: Path) -> None:
    with pytest.raises(DossierError, match="inconnu"):
        copier_modele(DepotFichiers(tmp_path), "ada", "inexistant")
