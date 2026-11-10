"""La copie du noyau reste alignée sur le moteur existant."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.services.assets import DWELLING_PARTS, _component_shares
from app.services.assets import add_months as legacy_months

from lmnp_core.depreciation import COMPOSANTS_DEFAUT, Plan, add_months, dotation, shares


def test_component_grid_matches_dwelling_parts() -> None:
    assert len(COMPOSANTS_DEFAUT) == len(DWELLING_PARTS)
    for ours, legacy in zip(COMPOSANTS_DEFAUT, DWELLING_PARTS, strict=True):
        _cle, _label, ratio, life, asset, amort = ours
        _legacy_label, legacy_ratio, legacy_life, legacy_asset, legacy_amort = legacy
        assert (ratio, life, asset, amort) == (
            legacy_ratio,
            legacy_life,
            legacy_asset,
            legacy_amort,
        )


def test_shares_and_months_match() -> None:
    for base in (0, 1, 99, 10_000, 3_051_670, 16_000_000):
        assert shares(base) == _component_shares(base)
    for start, months in (
        (date(2025, 1, 31), 1),
        (date(2024, 2, 29), 12),
        (date(2025, 7, 1), 480),
    ):
        assert add_months(start, months) == legacy_months(start, months)


def test_dotation_matches_calculate_year_formula() -> None:
    """Même arithmétique que calculate_year (assets.py, cumul arrondi moitié vers le haut)."""
    plan = Plan(
        "construction", "Construction", 3_051_670, 120, "213000", "281300", date(2025, 1, 1)
    )
    debut, fin = date(2025, 1, 1), date(2025, 12, 31)
    start = max(debut, plan.mise_en_service)
    end = min(fin, plan.fin)
    total_days = (plan.fin - plan.mise_en_service).days + 1
    before_days = max(0, (start - plan.mise_en_service).days)
    end_days = min(total_days, (end - plan.mise_en_service).days + 1)
    base = Decimal(plan.base)
    cumulative_before = int(
        (base * Decimal(before_days) / Decimal(total_days)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    accumulated = int(
        (base * Decimal(end_days) / Decimal(total_days)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    assert dotation(plan, debut, fin) == accumulated - cumulative_before
    assert dotation(plan, debut, fin) == 305_000
