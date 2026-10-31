import { cents } from "../api/ledger";
import type { Loan } from "../api/operations";

export type LoanPostingPath = "property_entry" | "funding";

/** Ledger movement exists. A missing flag falls back to a positive 164 balance. */
export function loanOnBalanceSheet(loan: Pick<Loan, "on_balance_sheet" | "remaining_principal">): boolean {
  if (typeof loan.on_balance_sheet === "boolean") return loan.on_balance_sheet;
  return cents(loan.remaining_principal) > 0n;
}

/** Contract figure, not a ledger balance. Positive only when account 164 is in credit. */
export function loanCapitalToRepay(loan: Pick<Loan, "remaining_principal">): boolean {
  return cents(loan.remaining_principal) > 0n;
}

export function loanPostingPath(loan: Loan): LoanPostingPath | null {
  if (loanOnBalanceSheet(loan)) return null;
  return loan.posting_path === "property_entry" ? "property_entry" : "funding";
}

/** Loans that already existed are taken up by the property entry. Others are drawn down. */
export function splitLoansForEntry(loans: readonly Loan[], exerciseStart: string | undefined): {
  entry: Loan[];
  drawdown: Loan[];
} {
  if (!exerciseStart) return { entry: [...loans], drawdown: [] };
  const entry: Loan[] = [];
  const drawdown: Loan[] = [];
  for (const loan of loans) {
    if (loan.start_date && loan.start_date >= exerciseStart) drawdown.push(loan);
    else entry.push(loan);
  }
  return { entry, drawdown };
}
