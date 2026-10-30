export interface ExportSlot {
  posture: "provisoire" | "bloquee" | "finale";
  label: string;
  download: boolean;
}

export interface ExportPrerequisite {
  code: string;
  message: string;
  export: string;
  action?: { label: string; href: string };
}

export interface ExportStatus {
  exports: Partial<Record<"liasse" | "pdf" | "fec" | "archive", ExportSlot>>;
  prerequisites?: ExportPrerequisite[];
}

export function asExportStatus(value: unknown): ExportStatus | null {
  if (!value || typeof value !== "object") return null;
  const exports = (value as { exports?: unknown }).exports;
  if (!exports || typeof exports !== "object") return null;
  return value as ExportStatus;
}
