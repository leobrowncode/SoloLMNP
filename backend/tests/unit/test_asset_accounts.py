"""Category and depreciation-account pairs, independent of the database."""

import pytest

from app.domain.assets.accounts import (
    category_of_account,
    mirror_depreciation_account,
    validate_asset_accounts,
    validate_component_accounts,
)


def test_mirror_matches_the_chart_length() -> None:
    assert mirror_depreciation_account("213000") == "281300"
    assert mirror_depreciation_account("213500") == "281350"
    assert mirror_depreciation_account("218300") == "281830"
    assert mirror_depreciation_account("218400") == "281840"
    assert mirror_depreciation_account("213100") == "281310"
    assert mirror_depreciation_account("212000") == "281200"
    assert mirror_depreciation_account("218100") == "281810"
    assert mirror_depreciation_account("213") is None
    assert mirror_depreciation_account("512000") is None
    assert mirror_depreciation_account("281300") is None


def test_longest_prefix_assigns_each_category() -> None:
    expected = {
        "211000": "LAND",
        "211100": "LAND",
        "212000": "BUILDING",
        "213000": "BUILDING",
        "213100": "BUILDING",
        "213500": "IMPROVEMENT",
        "214000": "BUILDING",
        "215000": "EQUIPMENT",
        "218100": "IMPROVEMENT",
        "218200": "EQUIPMENT",
        "218300": "EQUIPMENT",
        "218400": "FURNITURE",
        "218000": "OTHER",
        "218500": "OTHER",
    }
    for number, category in expected.items():
        assert category_of_account(number) == category
    assert category_of_account("281300") is None
    assert category_of_account("291000") is None
    assert category_of_account("231000") is None
    assert category_of_account("512000") is None


@pytest.mark.parametrize(
    ("category", "asset_account", "depreciation_account"),
    [
        ("LAND", "211000", None),
        ("BUILDING", "213000", "281300"),
        ("BUILDING", "213100", "281310"),
        ("IMPROVEMENT", "213500", "281350"),
        ("IMPROVEMENT", "218100", "281810"),
        ("EQUIPMENT", "218300", "281830"),
        ("EQUIPMENT", "215000", "281500"),
        ("FURNITURE", "218400", "281840"),
        ("OTHER", "218500", "281850"),
    ],
)
def test_validate_accepts_each_category(
    category: str, asset_account: str, depreciation_account: str | None
) -> None:
    validate_asset_accounts(category, asset_account, depreciation_account)


@pytest.mark.parametrize(
    ("category", "asset_account", "depreciation_account"),
    [
        ("BUILDING", "211000", "281300"),
        ("BUILDING", "281300", "281300"),
        ("BUILDING", "213000", "281840"),
        ("BUILDING", "213500", "281350"),
        ("FURNITURE", "213000", "281300"),
        ("FURNITURE", "218400", None),
        ("LAND", "213000", None),
        ("LAND", "211000", "281100"),
        ("OTHER", "218400", "281840"),
        ("EQUIPMENT", "512000", "281830"),
    ],
)
def test_validate_rejects_inconsistent_pairs(
    category: str, asset_account: str, depreciation_account: str | None
) -> None:
    with pytest.raises(ValueError):
        validate_asset_accounts(category, asset_account, depreciation_account)


def test_unknown_category_and_coarse_account_are_rejected() -> None:
    with pytest.raises(ValueError, match="inconnue"):
        validate_asset_accounts("VEHICLE", "218400", "281840")
    with pytest.raises(ValueError, match="4 chiffres"):
        validate_asset_accounts("BUILDING", "213", "2813")


def test_component_accepts_structure_and_installation_only() -> None:
    validate_component_accounts("213000", "281300")
    validate_component_accounts("213500", "281350")
    validate_component_accounts("218100", "281810")
    for asset_account, depreciation_account in (
        ("218400", "281840"),
        ("211000", "281100"),
        ("213000", "281350"),
        ("281300", "281300"),
        ("512000", "281300"),
    ):
        with pytest.raises(ValueError):
            validate_component_accounts(asset_account, depreciation_account)
