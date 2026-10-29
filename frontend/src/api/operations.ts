import { request } from "./ledger";
export const operationsRequest = <T>(path: string, method = "GET", body?: unknown) =>
  request<T>(path, method, body, "/api/operations");
interface CorrectionView {
  locks: { code: string; fields: string[]; message: string }[];
  calculated_periods: number;
}
export interface Property {
  id: number; name: string; address?: string; acquisition_date?: string;
  rental_start_date?: string | null; acquisition_price: string; acquisition_costs?: string;
  land_value: string; building_value: string; notes?: string;
  correction?: CorrectionView;
}
export interface Bank { id: number; name: string; account_number: string; correction?: CorrectionView }
export interface Loan {
  id: number; lender: string; property_id: number; initial_principal: string;
  remaining_principal: string; monthly_payment: string; monthly_insurance: string;
  principal_account: string; interest_rate_basis_points?: number;
  interest_rate?: string; start_date?: string; duration_months?: number; notes?: string;
  correction?: CorrectionView;
}
export interface Tenant {
  id: number; property_id: number; name: string; monthly_rent: string;
  entry_date: string; exit_date: string | null;
  correction?: CorrectionView;
}
export interface Operation {
  id: number; kind: string; property_id: number; fiscal_year_id: number; date: string;
  amount: string; description: string; counterparty: string; accounting_entry_id: number;
  remaining_to_settle: string | null; status: string; deductible_percentage: string; fiscal_treatment: string;
  principal: string; interest: string; insurance: string; other_costs: string;
}
export interface BankTransaction { id: number; date: string; label: string; amount: string; external_reference: string; matched_entry_id: number | null }
export interface ImportPreview { count: number; imported: number; rows: { date: string; label: string; amount: string; reference: string; duplicate: boolean; suggested_account: string | null }[] }
export interface OperationImportRow {
  kind: string; date: string; piece_date: string; type: string; accounting_account: string;
  counterparty: string; amount: string; description: string; piece_reference: string;
  source_file: string; duplicate: boolean; paid?: boolean;
}
export interface OperationImportPreview { count: number; imported: number; rows: OperationImportRow[] }
export interface LoanPaymentImportRow {
  loan_reference: string; rank: string; due_date: string; date: string; principal: string;
  interest: string; insurance: string; other_costs: string; amount: string; duplicate: boolean;
  piece_reference: string;
}
export interface LoanPaymentImportPreview {
  count: number; source_count: number; imported: number; outside_year: number; future: number;
  loan_reference: string; preview_token: string; rows: LoanPaymentImportRow[];
}
