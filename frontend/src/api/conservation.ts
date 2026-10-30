export interface EntryChoice {
  entry_number: string | null;
  accounting_date: string;
  piece_reference: string;
  piece_date: string;
  label: string;
  status: string;
  year: number;
}

export interface SupportingDocumentRow {
  id: number;
  original_name: string;
  created_at: string;
  media_type: string;
  media_label: string;
  size: number;
  sha256: string;
  entry: EntryChoice | null;
}

export interface IntegrityCheck {
  status: "unchecked" | "ok" | "failed";
  checked_at: string | null;
  message: string;
}

export interface BackupRow {
  filename: string;
  created_at: string;
  size: number;
  application_version: string | null;
  schema_revision: string | null;
  sha256: string;
  integrity: IntegrityCheck;
}

export interface RestorePreview {
  filename: string;
  backup_date: string;
  current: { entries: number; years: number };
  backup: { entries: number; years: number };
}

export function frStamp(value: string): string {
  const day = value.slice(0, 10);
  const [year, month, date] = day.split("-");
  if (!year || !month || !date) return value;
  const time = value.length >= 16 ? value.slice(11, 16) : "";
  return time ? `${date}/${month}/${year} ${time}` : `${date}/${month}/${year}`;
}

export function octets(size: number): string {
  return `${size.toLocaleString("fr-FR")} octets`;
}

export function entryLabel(entry: EntryChoice | null): string {
  if (!entry) return "Aucune";
  const number = entry.entry_number ?? "Brouillon";
  return `${number} · ${frStamp(entry.accounting_date)} · ${entry.piece_reference}`;
}

export function integrityLabel(check: IntegrityCheck): string {
  if (check.status === "ok") return `Réussi — ${check.message}`;
  if (check.status === "failed") return `Refusé — ${check.message}`;
  return check.message;
}
