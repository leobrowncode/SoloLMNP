"""LMNP réel simplifié, in integer cents. No database and no ledger writes.

The reading is the one stored in ``fiscal/<vintage>/rules.yaml``. A vintage
stays research-only; this module does not decide that a result is declarable.

Depreciation limit: CGI art. 39 C, II-2 and II-3. The deductible depreciation
of the year is the positive difference between rents and the other deductible
charges (BOI-BIC-AMT-20-40-10-20, 01/03/2017, II). The excluded fraction is
carried to later years under the same limit. It is not the amortissements
réputés différés abolished for years opened from 2004.

Tax loss: CGI art. 156, I, 1° ter. A non-professional furnished-rental deficit
is carried only against the same activity, for the ten following years. It is
not deducted from global income. Article 156, I, 1° bis is a different rule
and does not apply to this activity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TAX_LOSS_HORIZON_YEARS = 10
DEPRECIATION_RULE_ID = "RULE-LMNP-DEPRECIATION-LIMIT-001"
TAX_LOSS_RULE_ID = "RULE-LMNP-LOSS-001"

MovementKind = Literal["used", "expired"]


@dataclass(frozen=True)
class Stock:
    """One origin year, before the year being computed."""

    origin_year_id: int
    origin_year: int
    created: int
    used_before: int
    expired_before: int

    def remaining_before(self) -> int:
        return max(0, self.created - self.used_before - self.expired_before)


@dataclass(frozen=True)
class Movement:
    origin_year_id: int
    origin_year: int
    kind: MovementKind
    amount: int
    remaining_after: int


@dataclass(frozen=True)
class FiscalSplit:
    """Accounting result, adjustments and fiscally usable depreciation, apart."""

    accounting_result: int
    additions: int
    income: int
    other_charges: int
    accounting_depreciation: int
    capacity: int
    current_deductible: int
    unused_depreciation: int
    prior_depreciation_used: int
    depreciation_uses: tuple[Movement, ...]
    fiscal_before_losses: int
    prior_tax_loss_used: int
    tax_loss_uses: tuple[Movement, ...]
    tax_loss_expiries: tuple[Movement, ...]
    fiscal_result: int
    tax_loss: int


def apply_lmnp(
    *,
    year: int,
    income: int,
    other_charges: int,
    depreciation: int,
    additions: int,
    depreciation_stocks: tuple[Stock, ...] | list[Stock],
    tax_loss_stocks: tuple[Stock, ...] | list[Stock],
) -> FiscalSplit:
    """Split one year. Stocks must already be ordered from the oldest origin."""
    capacity = max(0, income - (other_charges - additions))
    current_deductible = min(max(0, depreciation), capacity)
    unused = max(0, depreciation) - current_deductible
    capacity_left = capacity - current_deductible
    depreciation_uses, prior_depreciation_used = _consume(
        [stock for stock in depreciation_stocks if stock.remaining_before() > 0],
        capacity_left,
    )
    deductible = current_deductible + prior_depreciation_used
    fiscal_before_losses = income - other_charges - deductible + additions
    expiries, usable = _expire_losses(year, tax_loss_stocks)
    loss_uses, prior_tax_loss_used = _consume(usable, max(0, fiscal_before_losses))
    fiscal_result = fiscal_before_losses - prior_tax_loss_used
    return FiscalSplit(
        accounting_result=income - other_charges - depreciation,
        additions=additions,
        income=income,
        other_charges=other_charges,
        accounting_depreciation=depreciation,
        capacity=capacity,
        current_deductible=current_deductible,
        unused_depreciation=unused,
        prior_depreciation_used=prior_depreciation_used,
        depreciation_uses=tuple(depreciation_uses),
        fiscal_before_losses=fiscal_before_losses,
        prior_tax_loss_used=prior_tax_loss_used,
        tax_loss_uses=tuple(loss_uses),
        tax_loss_expiries=tuple(expiries),
        fiscal_result=fiscal_result,
        tax_loss=max(0, -fiscal_result),
    )


def loss_is_inside_horizon(origin_year: int, current_year: int) -> bool:
    """True on each of the ten years that follow the origin year."""
    return origin_year >= current_year - TAX_LOSS_HORIZON_YEARS


def _expire_losses(
    year: int, stocks: tuple[Stock, ...] | list[Stock]
) -> tuple[list[Movement], list[Stock]]:
    expiries: list[Movement] = []
    usable: list[Stock] = []
    for stock in stocks:
        available = stock.remaining_before()
        if available <= 0:
            continue
        if loss_is_inside_horizon(stock.origin_year, year):
            usable.append(stock)
            continue
        expiries.append(
            Movement(
                origin_year_id=stock.origin_year_id,
                origin_year=stock.origin_year,
                kind="expired",
                amount=available,
                remaining_after=0,
            )
        )
    return expiries, usable


def _consume(stocks: list[Stock], budget: int) -> tuple[list[Movement], int]:
    remaining_budget = budget
    uses: list[Movement] = []
    used_total = 0
    for stock in stocks:
        if remaining_budget <= 0:
            break
        available = stock.remaining_before()
        take = min(available, remaining_budget)
        if take <= 0:
            continue
        remaining_budget -= take
        used_total += take
        uses.append(
            Movement(
                origin_year_id=stock.origin_year_id,
                origin_year=stock.origin_year,
                kind="used",
                amount=take,
                remaining_after=available - take,
            )
        )
    return uses, used_total
