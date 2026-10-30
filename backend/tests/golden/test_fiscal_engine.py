"""Hand-checked LMNP amounts. Expected cents are written here, not copied from the engine.

Sources consulted on 2026-10-30:

- CGI art. 39 C, II-2 and II-3, in force since 2015-01-01
  (https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000029355753/2015-01-01).
  Deductible depreciation cannot exceed rents minus the other charges. The
  excluded fraction is deducted in later years under the same limit.
- BOI-BIC-AMT-20-40-10-20 of 2017-03-01, II: the deductible amount is the
  positive difference. The worked example is rents 2 500, other charges
  1 000, depreciation 3 050, so 1 500 deductible and 1 550 carried forward.
- BOI-FORM-000038 carries the non-deducted balance to the next year and has
  no expiry column. Article 39 C, II states no ten-year cap. The engine
  therefore does not expire this stock.
- CGI art. 156, I, 1° ter, consolidated text in force since 2026-07-01
  (https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000053544806):
  an LMNP deficit is imputed only on income of the same activity during the
  ten following years. A 2015 deficit is still usable in 2025 (the tenth
  following year) and is expired in 2026. Article 156, I, 1° bis is not applied.
"""

from app.domain.fiscal.engine import Stock, apply_lmnp, loss_is_inside_horizon


def test_profitable_year_deducts_depreciation_inside_the_cap() -> None:
    # Rents 10 000, other charges 2 000, depreciation 3 000.
    # Capacity 8 000. The whole depreciation is deductible. No carry-forward.
    # Accounting result 5 000. Fiscal result 5 000.
    split = apply_lmnp(
        year=2026,
        income=1_000_000,
        other_charges=200_000,
        depreciation=300_000,
        additions=0,
        depreciation_stocks=[],
        tax_loss_stocks=[],
    )
    assert split.capacity == 800_000
    assert split.current_deductible == 300_000
    assert split.unused_depreciation == 0
    assert split.accounting_result == 500_000
    assert split.fiscal_result == 500_000
    assert split.tax_loss == 0
    assert split.additions == 0


def test_bofip_example_caps_depreciation_and_does_not_create_a_deficit() -> None:
    # BOI-BIC-AMT-20-40-10-20, II, example in euros: 2 500 / 1 000 / 3 050.
    # Deductible 1 500. Deferred 1 550. Accounting result -1 550. Fiscal result 0.
    split = apply_lmnp(
        year=2026,
        income=250_000,
        other_charges=100_000,
        depreciation=305_000,
        additions=0,
        depreciation_stocks=[],
        tax_loss_stocks=[],
    )
    assert split.capacity == 150_000
    assert split.current_deductible == 150_000
    assert split.unused_depreciation == 155_000
    assert split.accounting_result == -155_000
    assert split.fiscal_result == 0
    assert split.tax_loss == 0


def test_charges_create_the_deficit_and_depreciation_does_not_increase_it() -> None:
    # Rents 100, other charges 250, depreciation 800.
    # Capacity is the positive difference, so 0. Fiscal deficit stays 150.
    # Accounting result is -950 because the ledger keeps the full depreciation.
    split = apply_lmnp(
        year=2026,
        income=10_000,
        other_charges=25_000,
        depreciation=80_000,
        additions=0,
        depreciation_stocks=[],
        tax_loss_stocks=[],
    )
    assert split.capacity == 0
    assert split.current_deductible == 0
    assert split.unused_depreciation == 80_000
    assert split.accounting_result == -95_000
    assert split.fiscal_result == -15_000
    assert split.tax_loss == 15_000


def test_addition_raises_capacity_without_changing_the_accounting_result() -> None:
    # Rents 1 000, other charges 400 of which 100 are added back, depreciation 800.
    # Capacity 700. Accounting result stays 1 000 - 400 - 800 = -200.
    split = apply_lmnp(
        year=2026,
        income=100_000,
        other_charges=40_000,
        depreciation=80_000,
        additions=10_000,
        depreciation_stocks=[],
        tax_loss_stocks=[],
    )
    assert split.additions == 10_000
    assert split.capacity == 70_000
    assert split.current_deductible == 70_000
    assert split.unused_depreciation == 10_000
    assert split.accounting_result == -20_000
    assert split.fiscal_result == 0


def test_prior_depreciation_is_used_fifo_after_the_current_annuity() -> None:
    # Prior stocks 500 then 200. Year N+1: rents 1 000, other charges 200, depreciation 100.
    # Capacity 800. Current annuity 100. Both prior stocks are used (700).
    # Fiscal result 1 000 - 200 - 800 = 0. Accounting result 1 000 - 200 - 100 = 700.
    older = Stock(
        origin_year_id=1, origin_year=2024, created=50_000, used_before=0, expired_before=0
    )
    newer = Stock(
        origin_year_id=2, origin_year=2025, created=20_000, used_before=0, expired_before=0
    )
    split = apply_lmnp(
        year=2026,
        income=100_000,
        other_charges=20_000,
        depreciation=10_000,
        additions=0,
        depreciation_stocks=[older, newer],
        tax_loss_stocks=[],
    )
    assert split.current_deductible == 10_000
    assert split.prior_depreciation_used == 70_000
    assert split.unused_depreciation == 0
    assert [
        (move.origin_year, move.amount, move.remaining_after) for move in split.depreciation_uses
    ] == [
        (2024, 50_000, 0),
        (2025, 20_000, 0),
    ]
    assert split.fiscal_result == 0
    assert split.accounting_result == 70_000


def test_prior_loss_is_used_fifo_and_not_turned_into_a_global_deduction() -> None:
    # Prior LMNP losses 150 then 80. Profit before losses 400.
    # Use 150 then 80. Fiscal result 170, still an LMNP profit. New tax loss 0.
    first = Stock(
        origin_year_id=1, origin_year=2024, created=15_000, used_before=0, expired_before=0
    )
    second = Stock(
        origin_year_id=2, origin_year=2025, created=8_000, used_before=0, expired_before=0
    )
    split = apply_lmnp(
        year=2026,
        income=50_000,
        other_charges=10_000,
        depreciation=0,
        additions=0,
        depreciation_stocks=[],
        tax_loss_stocks=[first, second],
    )
    assert split.fiscal_before_losses == 40_000
    assert split.prior_tax_loss_used == 23_000
    assert [(move.origin_year, move.amount) for move in split.tax_loss_uses] == [
        (2024, 15_000),
        (2025, 8_000),
    ]
    assert split.fiscal_result == 17_000
    assert split.tax_loss == 0
    assert split.tax_loss_expiries == ()


def test_loss_expires_after_ten_following_years_and_depreciation_does_not() -> None:
    # 2015 loss: following years are 2016 through 2025. In 2026 it is expired.
    # 2016 loss: 2026 is the tenth following year, so it is still usable.
    # A 2000 depreciation stock is still usable: art. 39 C II has no ten-year cap.
    assert loss_is_inside_horizon(2015, 2025) is True
    assert loss_is_inside_horizon(2015, 2026) is False
    assert loss_is_inside_horizon(2016, 2026) is True
    expired = Stock(
        origin_year_id=1, origin_year=2015, created=15_000, used_before=0, expired_before=0
    )
    still_open = Stock(
        origin_year_id=2, origin_year=2016, created=10_000, used_before=0, expired_before=0
    )
    old_depreciation = Stock(
        origin_year_id=3, origin_year=2000, created=20_000, used_before=0, expired_before=0
    )
    split = apply_lmnp(
        year=2026,
        income=40_000,
        other_charges=0,
        depreciation=0,
        additions=0,
        depreciation_stocks=[old_depreciation],
        tax_loss_stocks=[expired, still_open],
    )
    assert [(move.origin_year, move.amount) for move in split.tax_loss_expiries] == [(2015, 15_000)]
    assert [
        (move.origin_year, move.amount, move.remaining_after) for move in split.tax_loss_uses
    ] == [(2016, 10_000, 0)]
    assert split.prior_depreciation_used == 20_000
    assert split.depreciation_uses[0].origin_year == 2000
    # 40 000 capacity, 20 000 depreciation used, 10 000 loss used. Fiscal result 10 000.
    assert split.fiscal_before_losses == 20_000
    assert split.fiscal_result == 10_000
    assert split.tax_loss == 0
