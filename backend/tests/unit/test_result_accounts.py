from app.domain.accounting.result_accounts import is_result_account, still_held


def test_result_accounts_are_120_and_129_except_dividend_advances():
    assert is_result_account("120000")
    assert is_result_account("120100")
    assert is_result_account("129000")
    assert not is_result_account("120900")
    assert not is_result_account("108000")
    assert not is_result_account("121000")


def test_closed_result_stays_on_the_account_until_it_leaves():
    assert still_held(0, {"120000": 80000}) == {"120000": 0}
    assert still_held(80000, {"120000": 80000}) == {"120000": 80000}
    assert still_held(80000, {"120000": 280000}) == {"120000": 80000}
    assert still_held(80000, {"120000": 0}) == {"120000": 0}
    assert still_held(-1001, {"129000": -1001}) == {"129000": -1001}
    assert still_held(80000, {"129000": -80000}) == {"129000": 0}
    assert still_held(80000, {"120000": 50000, "120100": 40000}) == {
        "120000": 50000,
        "120100": 30000,
    }
    assert still_held(50000, {"120000": 80000, "120100": 10000}) == {
        "120000": 50000,
        "120100": 0,
    }
