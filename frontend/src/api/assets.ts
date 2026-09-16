import { request } from "./ledger";

export const assetsRequest = <T>(path: string, method = "GET", body?: unknown) =>
  request<T>(path, method, body, "/api/assets");

export interface Component {
  id: number; asset_id: number; category: string; label: string; value: string;
  useful_life_months: number; service_start_date: string;
}
export interface Asset {
  id: number; property_id: number; category: string; label: string;
  acquisition_value: string; depreciable_value: string; non_depreciable_value: string;
  residual_value: string; useful_life_months: number | null; method: string;
  asset_account: string; depreciation_account: string | null; components: Component[];
}
export interface DepreciationPeriod {
  id: number; target_type: string; target_id: number; target_label: string; base: string;
  period_start: string; period_end: string; days: number; amount: string;
  accumulated: string; net_book_value: string; status: string;
  accounting_entry_id: number | null; depreciation_account: string;
}
