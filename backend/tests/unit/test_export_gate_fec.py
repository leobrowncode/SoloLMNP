"""A blocked liasse explains the FEC in plain French, with a link."""

from app.domain.fiscal.output_status import export_slot
from app.services.export_gate import _prerequisites


def test_closed_blocked_liasse_copies_the_reason_onto_the_fec() -> None:
    items = _prerequisites(
        produced=True,
        year_closed=True,
        siren_ok=True,
        fec_errors=[],
        blocking=[
            {
                "code": "CLASSEMENT_INCOMPLET",
                "message": "Le classement du 2033-E est incomplet.",
            }
        ],
        exports={
            "liasse": export_slot("bloquee"),
            "pdf": export_slot("bloquee"),
            "fec": export_slot("bloquee"),
            "archive": export_slot("bloquee"),
        },
    )
    fec = [item for item in items if item["export"] == "fec"]
    assert len(fec) == 1
    assert fec[0]["code"] == "CLASSEMENT_INCOMPLET"
    assert "2033-E" in fec[0]["message"]
    assert fec[0]["action"]["href"].startswith("/fiscalite")
    assert fec[0]["action"]["label"]
    assert "Finale" not in fec[0]["message"]


def test_open_year_still_points_the_fec_at_the_close() -> None:
    items = _prerequisites(
        produced=True,
        year_closed=False,
        siren_ok=True,
        fec_errors=[],
        blocking=[],
        exports={
            "liasse": export_slot("provisoire"),
            "pdf": export_slot("provisoire"),
            "fec": export_slot("bloquee"),
            "archive": export_slot("bloquee"),
        },
    )
    fec = next(item for item in items if item["export"] == "fec")
    assert fec["code"] == "YEAR_NOT_CLOSED"
    assert "clôturé" in fec["message"]
    assert fec["action"]["href"] == "/fiscalite#close-title"
