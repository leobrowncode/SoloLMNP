from app.core.csv_text import safe_cell


def test_safe_cell_neutralizes_formula_prefixes() -> None:
    assert safe_cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert safe_cell("+cmd") == "'+cmd"
    assert safe_cell("@sum") == "'@sum"
    assert safe_cell("-note") == "'-note"
    assert safe_cell("-12,50") == "-12,50"
    assert safe_cell("Loyer") == "Loyer"
