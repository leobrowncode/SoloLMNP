import { request } from "./ledger";
export const operationsRequest = <T>(path: string, method = "GET", body?: unknown) =>
  request<T>(path, method, body, "/api/operations");
export interface Property { id: number; name: string; acquisition_price: string; land_value: string; building_value: string }
export interface Bank { id: number; name: string; account_number: string }
export interface Loan { id: number; lender: string; property_id: number; initial_principal: string; remaining_principal: string; monthly_payment: string; monthly_insurance: string; principal_account: string }
export interface Operation {
  id: number; kind: string; property_id: number; fiscal_year_id: number; date: string;
  amount: string; description: string; counterparty: string; accounting_entry_id: number;
  remaining_to_settle: string | null; status: string; deductible_percentage: string; fiscal_treatment: string;
  principal: string; interest: string; insurance: string; other_costs: string;
}
export interface BankTransaction { id: number; date: string; label: string; amount: string; external_reference: string; matched_entry_id: number | null }
export interface ImportPreview { count: number; imported: number; rows: { date: string; label: string; amount: string; reference: string; duplicate: boolean; suggested_account: string | null }[] }
