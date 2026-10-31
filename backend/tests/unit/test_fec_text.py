"""FEC text zones stay 18 columns and are not spreadsheet formulas."""

from app.domain.filing.fec import COLUMNS, _format, fec_text


def test_fec_text_neutralizes_formulas_and_keeps_the_zone_count() -> None:
    assert fec_text("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert fec_text("+cmd") == "'+cmd"
    assert fec_text("@sum") == "'@sum"
    assert fec_text("Loyer") == "Loyer"
    assert "\t" not in fec_text("lib\tellé")
    assert "\n" not in fec_text("ligne\r\nsuivante")
    assert fec_text("10,00") == "10,00"

    row = {column: "" for column in COLUMNS}
    row["EcritureLib"] = fec_text("=CMD|A\tB")
    row["PieceRef"] = fec_text("PIECE")
    row["Debit"] = "10,00"
    row["Credit"] = "0,00"
    row["EcritureDate"] = "20251231"
    line = _format(row)
    assert line.endswith("\r\n")
    cells = line.removesuffix("\r\n").split("\t")
    assert len(cells) == 18
    assert cells[COLUMNS.index("EcritureLib")] == "'=CMD|A B"
    assert cells[COLUMNS.index("Debit")] == "10,00"
    assert cells[COLUMNS.index("Credit")] == "0,00"
    assert cells[COLUMNS.index("EcritureDate")] == "20251231"
    assert line.count("\t") == 17
