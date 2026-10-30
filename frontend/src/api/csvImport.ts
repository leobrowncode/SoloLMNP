import { parseApiErrorDetail, type ApiErrorIssue } from "./errors";
import { RequestError } from "./ledger";

export type CsvProfile = "bank" | "operations" | "loan_payments";

export interface CsvField {
  key: string;
  label: string;
  required: boolean;
  help: string;
}

export interface CsvRow {
  line: number;
  status: "valid" | "duplicate" | "warning" | "error";
  importable: boolean;
  duplicate: boolean;
  display: Record<string, string>;
  issues: ApiErrorIssue[];
  warnings: ApiErrorIssue[];
  suggested_account: string | null;
}

export interface CsvSummary {
  valid: number;
  duplicate: number;
  warning: number;
  error: number;
  count: number;
  importable: number;
}

export interface CsvPreview {
  profile: CsvProfile;
  ready: boolean;
  delimiter: string;
  headers: string[];
  fields: CsvField[];
  mapping: Record<string, string>;
  issues: ApiErrorIssue[];
  rows: CsvRow[];
  summary: CsvSummary;
  rejects_csv: string;
  loan_reference: string | null;
  imported: number;
}

export interface CsvInspect {
  delimiter: string;
  headers: string[];
  fields: Record<CsvProfile, CsvField[]>;
  suggestions: Record<CsvProfile, Record<string, string>>;
}

export async function downloadImportTemplate(profile: CsvProfile): Promise<void> {
  const response = await fetch(`/api/operations/imports/${profile}/template`, {
    method: "GET",
    cache: "no-store",
    headers: { "X-SoloLMNP-Request": "1", Accept: "text/csv, application/json" },
  });
  if (!response.ok) {
    let detail;
    try {
      const data = await response.json() as { detail?: unknown };
      detail = parseApiErrorDetail(data.detail as Parameters<typeof parseApiErrorDetail>[0]);
    } catch {
      detail = parseApiErrorDetail(undefined);
    }
    throw new RequestError(detail, response.status);
  }
  const blob = await response.blob();
  const name = filenameFrom(response.headers.get("Content-Disposition"));
  saveBlob(blob, name);
}

export function downloadRejects(filename: string, csv: string): void {
  saveBlob(new Blob([csv], { type: "text/csv;charset=utf-8" }), filename);
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function filenameFrom(header: string | null): string {
  const match = header ? /filename="([^"]+)"/.exec(header) : null;
  return match?.[1] || "modele.csv";
}
