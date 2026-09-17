export interface Year { id: number; year: number; start_date: string; end_date: string; status: string }
export interface Setup { activity: { activity_name: string } | null; years: Year[] }
export interface Account { number: string; label: string; account_type: string; active: boolean }
export interface Journal { code: string; label: string; active: boolean; journal_type?: string }
export interface Line { account_number: string; label: string; debit: string; credit: string }
export interface EntryLine extends Line { id: number; position: number; account_label: string | null }
export interface EntryInput {
  fiscal_year_id: number; journal_code: string; accounting_date: string;
  piece_reference: string; piece_date: string; label: string; lines: Line[];
}
export interface Entry extends Omit<EntryInput, "lines"> {
  lines: EntryLine[];
  id: number; version: number; status: string; entry_number: string | null;
  total_debit: string; total_credit: string; balanced: boolean; reversal_of_id: number | null;
}
export interface BalanceRow { account_number: string; label: string; total_debit: string; total_credit: string; debit_balance: string; credit_balance: string }
export interface Balance { balance: BalanceRow[]; total_debit: string; total_credit: string; balanced: boolean }
export interface LedgerLine { entry_id: number; entry_number: string; date: string; label: string; debit: string; credit: string; balance: string }
export async function request<T>(path: string, method = "GET", body?: unknown, prefix = "/api/ledger"): Promise<T> {
  const response = await fetch(prefix + path, {
    method, cache: "no-store",
    headers: { "Content-Type": "application/json", "X-SoloLMNP-Request": "1" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json() as { detail?: { message?: string } | unknown[] };
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(detail && !Array.isArray(detail) && detail.message
      ? detail.message : "Opération refusée. Vérifiez les champs, les dates et les montants au centime.");
  }
  return data as T;
}
// Browser arithmetic uses integer cents; money never passes through Number.
export function cents(value: string): bigint {
  if (!/^\d+(?:[.,]\d{1,2})?$/.test(value)) throw new Error("Montant au centime requis.");
  const [whole = "0", fraction = ""] = value.replace(",", ".").split(".");
  return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
}
export function amount(value: bigint): string {
  const sign = value < 0n ? "-" : "";
  const absolute = value < 0n ? -value : value;
  return sign + String(absolute / 100n) + "." + String(absolute % 100n).padStart(2, "0");
}
