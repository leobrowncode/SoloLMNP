"""A 2033 line lists each source writing once, even when it posts to several accounts."""

from app.domain.filing.mappings import _eval, _named


def test_sum_accounts_lists_a_shared_entry_once() -> None:
    context = {
        "balances": {"616000": 1000, "681100": 500},
        "entries": {"616000": [10, 2], "681100": [4, 10]},
        "tax_result": 0,
        "named": {},
    }
    value, accounts, entries = _eval(
        {"op": "sum_accounts", "prefixes": ["6"]},
        context,
        [],
        "CHARGES",
    )
    assert value == 1500
    assert accounts == ["616000", "681100"]
    assert entries == [10, 2, 4]


def test_named_buckets_list_the_closing_entry_once() -> None:
    fiscal = {
        "accounting_result": "500.00",
        "fiscal_result": "500.00",
        "unused_depreciation": "0.00",
        "non_deductible": "0.00",
        "details": {},
    }
    named = _named(
        {"616000": 1000, "681100": 500},
        {"706000": 2000},
        {"616000": [2, 10], "681100": [4, 10], "706000": [1, 10]},
        fiscal,
    )
    assert named["exploitation_charges"][2] == [2, 10, 4]
    assert named["operating_result"][2].count(10) == 1
    assert named["operating_result"][2] == [1, 10, 2, 4]
