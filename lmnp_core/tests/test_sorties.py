"""Feuille EFI, traces, PDF, suivi 39 C, archive SHA-256."""

import io
import json
import zipfile
from pathlib import Path

from lmnp_core.build import build_path
from lmnp_core.sorties import produire

ROOT = Path(__file__).resolve().parents[2]


def test_efi_order_traces_and_archive() -> None:
    result = build_path(ROOT / "golden" / "premier-exercice" / "input")
    first = produire(result)
    second = produire(result)
    assert first["archive_sha256"] == second["archive_sha256"]
    assert first["fec"]["valide"]
    sheet = first["efi"]
    assert isinstance(sheet, dict)
    assert sheet["ok"]
    assert sheet["ordre_ecrans"][:5] == ["2033-A", "2033-C", "2033-B", "2033-D", "2033-E"]
    assert sheet["transmission"] is False
    lignes = sheet["lignes"]
    assert isinstance(lignes, list)
    assert lignes[0]["ecran"] == "2033-A"
    neant = [row for row in lignes if row["ecran"] == "2033-D"]
    assert neant[0]["montant"] == "neant"
    expected = json.loads(
        (ROOT / "golden" / "premier-exercice" / "expected.json").read_text(encoding="utf-8")
    )
    traces = first["traces"]
    assert isinstance(traces, dict)
    for case in expected["annees"]["2025"]["cases"]:
        trace = traces[case]
        assert trace["comptes"] or trace["origine"]
    loyer = traces["2033-B-SD/242"]
    assert "614000" in loyer["comptes"]
    assert loyer["ecritures"]
    _pdf_contient(first, "liasse.pdf", b"202400,00")
    _pdf_contient(first, "2042-c-pro.pdf", b"5NA")


def test_suivi_cap_and_next_year() -> None:
    capped = produire(build_path(ROOT / "golden" / "plafond-39c" / "input"))
    suivi = capped["suivi"]
    assert isinstance(suivi, dict)
    assert suivi["stock_fin"][0]["restant_centimes"] == 155000
    deficit = produire(build_path(ROOT / "golden" / "deficit-imputation" / "input"))
    etat = deficit["suivi"]
    assert isinstance(etat, dict)
    assert etat["stock_fin"] == []
    assert any(row["mouvement"] == "impute" and row["centimes"] == 80000 for row in etat["lignes"])
    assert deficit["fec"]["valide"]


def _pdf_contient(produit: dict[str, object], name: str, needle: bytes) -> None:
    archive = produit["archive"]
    assert isinstance(archive, bytes)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        payload = bundle.read(name)
        sommes = bundle.read("SHA256SUMS.txt").decode()
    assert payload.startswith(b"%PDF")
    assert needle in payload
    assert name in sommes
