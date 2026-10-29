"""Allowed fixed-asset account pairs.

The chart keeps asset and depreciation numbers the same length. The depreciation
account inserts ``8`` after the class digit and drops the final padding digit:
``213000`` → ``281300``, ``213500`` → ``281350``, ``218400`` → ``281840``.

Land (``211``) has no depreciation account. Accounts ``28`` and ``29`` are never
asset accounts. A pair already stored is not rewritten; callers only report it.
"""

from dataclasses import dataclass


class AssetAccountError(ValueError):
    """Category and account numbers do not form an allowed pair."""


@dataclass(frozen=True, slots=True)
class CategoryAccounts:
    label: str
    expectation: str
    default_asset: str | None
    default_depreciation: str | None


# Longest matching prefix wins, so 2135 is not treated as a plain 213.
_PREFIXES: tuple[tuple[str, str], ...] = (
    ("2135", "IMPROVEMENT"),
    ("2181", "IMPROVEMENT"),
    ("2182", "EQUIPMENT"),
    ("2183", "EQUIPMENT"),
    ("2184", "FURNITURE"),
    ("211", "LAND"),
    ("212", "BUILDING"),
    ("213", "BUILDING"),
    ("214", "BUILDING"),
    ("215", "EQUIPMENT"),
    ("218", "OTHER"),
)

CATEGORIES: dict[str, CategoryAccounts] = {
    "LAND": CategoryAccounts("Terrain", "211", "211000", None),
    "BUILDING": CategoryAccounts("Construction", "212, 213 (sauf 2135) ou 214", "213000", "281300"),
    "IMPROVEMENT": CategoryAccounts("Travaux immobilisés", "2135 ou 2181", "213500", "281350"),
    "EQUIPMENT": CategoryAccounts("Équipement", "215, 2182 ou 2183", "218300", "281830"),
    "FURNITURE": CategoryAccounts("Mobilier", "2184", "218400", "281840"),
    "OTHER": CategoryAccounts(
        "Autre immobilisation",
        "218, hors 2181, 2182, 2183 et 2184",
        None,
        None,
    ),
}

COMPONENT_CATEGORIES = frozenset({"BUILDING", "IMPROVEMENT"})
COMPONENT_EXPECTATION = "212, 213, 214, 2135 ou 2181"
_MIN_ASSET_LENGTH = 4


def category_of_account(number: str) -> str | None:
    """Return the immobilisation category that owns this account, if any."""
    best: tuple[int, str] | None = None
    for prefix, category in _PREFIXES:
        if number.startswith(prefix) and (best is None or len(prefix) > best[0]):
            best = (len(prefix), category)
    return None if best is None else best[1]


def mirror_depreciation_account(asset_account: str) -> str | None:
    """Return the same-length 28 account, or None when the number is too coarse."""
    if len(asset_account) < _MIN_ASSET_LENGTH or not asset_account.startswith("21"):
        return None
    return "28" + asset_account[1:-1]


def validate_asset_accounts(
    category: str, asset_account: str, depreciation_account: str | None
) -> None:
    """Reject a category / asset account / depreciation account combination."""
    rule = CATEGORIES.get(category)
    if rule is None:
        raise AssetAccountError("Catégorie d’immobilisation inconnue.")
    _reject_contra_asset(asset_account, rule.expectation)
    found = category_of_account(asset_account)
    if found != category:
        if found is None:
            raise AssetAccountError(
                f"Le compte {asset_account} n’est pas un compte d’immobilisation "
                f"de {rule.label}. Comptes attendus : {rule.expectation}."
            )
        other = CATEGORIES[found].label
        raise AssetAccountError(
            f"Le compte {asset_account} correspond à {other}, pas à {rule.label}. "
            f"Comptes attendus : {rule.expectation}."
        )
    if category == "LAND":
        if depreciation_account is not None:
            raise AssetAccountError("Un terrain n’a pas de compte d’amortissement.")
        return
    _require_mirror(asset_account, depreciation_account)


def validate_component_accounts(asset_account: str, depreciation_account: str) -> None:
    """A building component uses a construction or fitting account and its mirror."""
    _reject_contra_asset(asset_account, COMPONENT_EXPECTATION)
    found = category_of_account(asset_account)
    if found not in COMPONENT_CATEGORIES:
        raise AssetAccountError(
            "Un composant de construction utilise un compte "
            f"{COMPONENT_EXPECTATION}. Le compte {asset_account} n’est pas autorisé."
        )
    _require_mirror(asset_account, depreciation_account)


def _reject_contra_asset(number: str, expectation: str) -> None:
    if number.startswith(("28", "29")):
        raise AssetAccountError(
            f"Le compte {number} est un compte d’amortissement ou de dépréciation. "
            f"Le compte d’immobilisation attendu est : {expectation}."
        )


def _require_mirror(asset_account: str, depreciation_account: str | None) -> None:
    mirror = mirror_depreciation_account(asset_account)
    if mirror is None:
        raise AssetAccountError(
            f"Le compte {asset_account} ne permet pas de déterminer un compte "
            "d’amortissement. Utilisez au moins 4 chiffres, par exemple 213000."
        )
    if depreciation_account != mirror:
        given = depreciation_account or "aucun compte"
        raise AssetAccountError(
            f"Le compte d’amortissement associé à {asset_account} est {mirror}, pas {given}."
        )
