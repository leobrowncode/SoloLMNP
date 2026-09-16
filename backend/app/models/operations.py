"""Business records are immutable links to validated ledger entries."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, utc_now


class BankAccount(Base):
    __tablename__ = "bank_account"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    account_number: Mapped[str] = mapped_column(ForeignKey("account.number"), unique=True)


class Loan(Base):
    __tablename__ = "loan"
    __table_args__ = (
        CheckConstraint(
            "typeof(initial_principal)='integer' AND initial_principal>0", name="principal"
        ),
        CheckConstraint(
            "typeof(monthly_payment)='integer' AND monthly_payment>=0 AND "
            "typeof(monthly_insurance)='integer' AND monthly_insurance>=0",
            name="monthly_terms",
        ),
        CheckConstraint("duration_months>0 AND interest_rate_basis_points>=0", name="terms"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("property.id"), index=True)
    lender: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date)
    initial_principal: Mapped[Decimal] = mapped_column(Money)
    interest_rate_basis_points: Mapped[int]
    duration_months: Mapped[int]
    monthly_payment: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"))
    monthly_insurance: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"))
    principal_account: Mapped[str] = mapped_column(ForeignKey("account.number"), unique=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class BusinessOperation(Base):
    __tablename__ = "business_operation"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('REVENUE','EXPENSE','SETTLEMENT','LOAN_PAYMENT','LOAN_FUNDING')", name="kind"
        ),
        CheckConstraint("typeof(amount)='integer' AND amount>0", name="amount"),
        CheckConstraint("deductible_basis_points BETWEEN 0 AND 10000", name="percentage"),
        CheckConstraint(
            "(fiscal_treatment='REQUIRES_REVIEW') OR "
            "(fiscal_treatment='DEDUCTIBLE' AND deductible_basis_points=10000) OR "
            "(fiscal_treatment='NON_DEDUCTIBLE' AND deductible_basis_points=0) OR "
            "(fiscal_treatment='PARTIAL' AND deductible_basis_points BETWEEN 1 AND 9999)",
            name="fiscal_metadata",
        ),
        CheckConstraint(
            "kind='LOAN_PAYMENT' OR (principal=0 AND interest=0 AND insurance=0 AND other_costs=0)",
            name="loan_components",
        ),
        *(
            CheckConstraint(f"typeof({name})='integer' AND {name}>=0", name=name)
            for name in ("principal", "interest", "insurance", "other_costs")
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(20))
    property_id: Mapped[int] = mapped_column(ForeignKey("property.id"), index=True)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_year.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Money)
    description: Mapped[str] = mapped_column(String(300))
    counterparty: Mapped[str] = mapped_column(String(200), default="")
    accounting_account: Mapped[str] = mapped_column(ForeignKey("account.number"))
    bank_account_id: Mapped[int | None] = mapped_column(ForeignKey("bank_account.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("business_operation.id"), index=True)
    loan_id: Mapped[int | None] = mapped_column(ForeignKey("loan.id"), index=True)
    accounting_entry_id: Mapped[int] = mapped_column(ForeignKey("accounting_entry.id"), unique=True)
    deductible_basis_points: Mapped[int] = mapped_column(default=10000)
    fiscal_treatment: Mapped[str] = mapped_column(String(40), default="REQUIRES_REVIEW")
    principal: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"))
    interest: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"))
    insurance: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"))
    other_costs: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class BankTransaction(Base):
    __tablename__ = "bank_transaction"
    __table_args__ = (
        UniqueConstraint("bank_account_id", "external_reference"),
        CheckConstraint("typeof(amount)='integer' AND amount!=0", name="amount"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("bank_account.id"), index=True)
    external_reference: Mapped[str] = mapped_column(String(200))
    date: Mapped[date] = mapped_column(Date)
    label: Mapped[str] = mapped_column(String(300))
    amount: Mapped[Decimal] = mapped_column(Money)
    fingerprint: Mapped[str] = mapped_column(String(64))
    import_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class BankMatch(Base):
    __tablename__ = "bank_match"
    transaction_id: Mapped[int] = mapped_column(ForeignKey("bank_transaction.id"), primary_key=True)
    entry_line_id: Mapped[int] = mapped_column(ForeignKey("accounting_entry_line.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
