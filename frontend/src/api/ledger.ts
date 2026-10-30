import {
  errorSummary,
  parseApiErrorDetail,
  type ApiErrorAction,
  type ApiErrorDetail,
  type ApiErrorIssue,
} from "./errors";
import { AMOUNT_INPUT_ERROR, centsToApiAmount, parseAmountToCents } from "../lib/format";

export interface Year { id: number; year: number; start_date: string; end_date: string; status: string }

export interface Setup {
  activity: { activity_name: string; siren?: string | null; siret?: string | null } | null;
  years: Year[];
}
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

export type { ApiErrorAction, ApiErrorDetail, ApiErrorIssue };

export class RequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: ApiErrorDetail;

  constructor(detail: ApiErrorDetail, status: number) {
    super(errorSummary(detail));
    this.name = "RequestError";
    this.status = status;
    this.code = detail.code;
    this.detail = detail;
  }
}

export interface RequestOptions {
  headers?: Record<string, string>;
}

export async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
  prefix = "/api/ledger",
  options?: RequestOptions,
): Promise<T> {
  const response = await fetch(prefix + path, {
    method, cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-SoloLMNP-Request": "1",
      ...options?.headers,
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json() as { detail?: unknown };
  if (!response.ok) {
    throw new RequestError(parseApiErrorDetail(data.detail as Parameters<typeof parseApiErrorDetail>[0]), response.status);
  }
  return data as T;
}
// Browser arithmetic uses integer cents; money never passes through Number.
export function cents(value: string): bigint {
  const parsed = parseAmountToCents(value);
  if (parsed < 0n) throw new Error(AMOUNT_INPUT_ERROR);
  return parsed;
}
export function amount(value: bigint): string {
  return centsToApiAmount(value);
}
