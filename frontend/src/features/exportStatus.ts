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
  output_status?: string;
  output_label?: string;
  exports: Partial<Record<"liasse" | "pdf" | "fec" | "archive", ExportSlot>>;
  prerequisites?: ExportPrerequisite[];
}

const EXPORT_KINDS = ["liasse", "pdf", "fec", "archive"] as const;

/** The shared sentence is true only when every output carries the same posture,
 * and that posture does not outrank the calculation. */
export function sameStatusClaim(status: {
  output_status?: string;
  exports?: ExportStatus["exports"];
}): boolean {
  if (!status.exports) return false;
  const postures = EXPORT_KINDS.map((kind) => status.exports?.[kind]?.posture);
  const first = postures[0];
  if (first !== "provisoire" && first !== "bloquee" && first !== "finale") return false;
  if (!postures.every((item) => item === first)) return false;
  if (first === "finale") return status.output_status === "declarable";
  if (first === "bloquee") return false;
  return status.output_status === "recherche" || status.output_status === "provisoire";
}

export function asExportStatus(value: unknown): ExportStatus | null {
  if (!value || typeof value !== "object") return null;
  const exports = (value as { exports?: unknown }).exports;
  if (!exports || typeof exports !== "object") return null;
  return value as ExportStatus;
}
