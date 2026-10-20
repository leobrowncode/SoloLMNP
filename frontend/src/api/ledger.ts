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
export const REFUSAL = "Opération refusée. Vérifiez les champs, les dates et les montants au centime.";

function refusalText(value: unknown, stripPrefix: boolean): string {
  if (typeof value !== "string") return "";
  const text = stripPrefix ? value.replace(/^Value error,\s*/i, "") : value;
  return text.trim().slice(0, 500);
}

// Domain refusals use detail.message. Pydantic validation uses detail[].msg
// and prefixes the French sentence with "Value error, ". The input payload
// is never copied into the message shown to the user.
export function refusalMessage(payload: unknown): string {
  const detail = payload && typeof payload === "object" ? (payload as { detail?: unknown }).detail : undefined;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => refusalText(
      item && typeof item === "object" ? (item as { msg?: unknown }).msg : item, true,
    )).filter(Boolean);
    return messages.join(" ") || REFUSAL;
  }
  const message = typeof detail === "string"
    ? refusalText(detail, false)
    : refusalText(detail && typeof detail === "object" ? (detail as { message?: unknown }).message : "", false);
  return message || REFUSAL;
}

export async function request<T>(path: string, method = "GET", body?: unknown, prefix = "/api/ledger"): Promise<T> {
  const response = await fetch(prefix + path, {
    method, cache: "no-store",
    headers: { "Content-Type": "application/json", "X-SoloLMNP-Request": "1" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error(response.ok ? "Réponse du service illisible." : REFUSAL);
  }
  if (!response.ok) throw new Error(refusalMessage(data));
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
