import { request, type RequestOptions } from "./ledger";

export const assetsRequest = <T>(
  path: string,
  method = "GET",
  body?: unknown,
  options?: RequestOptions,
) => request<T>(path, method, body, "/api/assets", options);

export interface Component {
  id: number; asset_id: number; category: string; label: string; value: string;
  useful_life_months: number; service_start_date: string;
  asset_account?: string; depreciation_account?: string;
  basis_reason?: string; duration_reason?: string;
  account_warning?: string | null;
  correction?: {
    locks: { code: string; fields: string[]; message: string }[];
    calculated_periods: number;
  };
}
export interface Asset {
  id: number; property_id: number; category: string; label: string;
  acquisition_date?: string; service_start_date?: string;
  acquisition_value: string; depreciable_value: string; non_depreciable_value: string;
  residual_value: string; useful_life_months: number | null; method: string;
  asset_account: string; depreciation_account: string | null; components: Component[];
  basis_reason?: string; duration_reason?: string; notes?: string;
  account_warning?: string | null;
  correction?: {
    locks: { code: string; fields: string[]; message: string }[];
    calculated_periods: number;
  };
}
export interface DepreciationPeriod {
  id: number; target_type: string; target_id: number; target_label: string; base: string;
  period_start: string; period_end: string; days: number; amount: string;
  accumulated: string; net_book_value: string; status: string;
  accounting_entry_id: number | null; depreciation_account: string;
  asset_on_ledger?: boolean;
  booking?: "ok" | "entry" | "journal";
}
export interface DepreciationBatchItemResult {
  period_id: number;
  status: "posted" | "error" | "skipped";
  entry_id?: number;
  replayed?: boolean;
  code?: string;
  message?: string;
  action?: { label: string; href: string };
}
export interface DepreciationBatchResult {
  idempotency_key: string;
  replayed: boolean;
  posted_count: number;
  failed_count: number;
  skipped_count: number;
  items: DepreciationBatchItemResult[];
}
