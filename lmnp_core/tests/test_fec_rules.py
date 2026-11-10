"""Le validateur rejoue A47 A-1. L'outil Windows n'est pas lancé."""

from datetime import date
from pathlib import Path

from app.domain.filing.fec import COLUMNS

from lmnp_core.build import build_path
from lmnp_core.fec_rules import OUTIL_OFFICIEL, controler

ROOT = Path(__file__).resolve().parents[2]
DEBUT = date(2025, 7, 1)
FIN = date(2025, 12, 31)


def test_golden_fec_has_no_blocking_anomaly() -> None:
    result = build_path(ROOT / "golden" / "premier-exercice" / "input")
    report = controler(result.annee(2025).fec_texte.encode(), DEBUT, FIN)
    assert report["valide"]
    assert report["bloquantes"] == []
    assert any(item["code"] == "AN_ABSENT" for item in report["avertissements"])
    assert "Windows" in OUTIL_OFFICIEL


def test_structure_balance_and_pairs() -> None:
    result = build_path(ROOT / "golden" / "premier-exercice" / "input")
    original = result.annee(2025).fec_texte
    assert not controler(b"pas un fec\r\n", DEBUT, FIN)["valide"]
    unbalanced = original.replace("2000,00", "1,00", 1)
    report = controler(unbalanced.encode(), DEBUT, FIN)
    assert any(item["code"] == "DESEQUILIBRE" for item in report["bloquantes"])
    warned = controler(_deux_sens(), DEBUT, FIN)
    assert any(item["code"] == "DEUX_SENS" for item in warned["avertissements"])
    assert warned["valide"]
    nul = controler(_montant_nul(), DEBUT, FIN)
    assert any(item["code"] == "MONTANT_NUL" for item in nul["avertissements"])
    assert nul["valide"]
    paired = _auxiliaire_seul(original)
    aux = controler(paired.encode(), DEBUT, FIN)
    assert any(item["code"] == "AUXILIAIRE" for item in aux["bloquantes"])


def _deux_sens() -> bytes:
    return _fichier(debit="10,00", credit="10,00")


def _montant_nul() -> bytes:
    return _fichier(debit="0,00", credit="0,00")


def _fichier(*, debit: str, credit: str) -> bytes:
    row = dict.fromkeys(COLUMNS, "")
    row.update(
        {
            "JournalCode": "OD",
            "JournalLib": "Operations diverses",
            "EcritureNum": "1",
            "EcritureDate": "20250701",
            "CompteNum": "512000",
            "CompteLib": "Banque",
            "PieceRef": "TEST",
            "PieceDate": "20250701",
            "EcritureLib": "Ligne de controle",
            "Debit": debit,
            "Credit": credit,
            "ValidDate": "20250701",
        }
    )
    body = "\t".join(row[column] for column in COLUMNS)
    return ("\t".join(COLUMNS) + "\r\n" + body + "\r\n").encode()


def _auxiliaire_seul(payload: str) -> str:
    lines = payload.split("\r\n")
    cells = lines[1].split("\t")
    cells[6] = "AUX"
    lines[1] = "\t".join(cells)
    return "\r\n".join(lines)
