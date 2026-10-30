export interface DossierStatus {
  status: "incomplet" | "bloque" | "pret_a_verifier" | "cloture";
  label: "Incomplet" | "Bloqué" | "Prêt à vérifier" | "Clôturé";
  fiscal_year_id: number | null;
  year: number | null;
  year_status: "OPEN" | "READY_TO_CLOSE" | "CLOSED" | null;
  vintage_status: "research_only";
}

export const DOSSIER_LABELS = {
  incomplet: "Incomplet",
  bloque: "Bloqué",
  pret_a_verifier: "Prêt à vérifier",
  cloture: "Clôturé",
} as const satisfies Record<DossierStatus["status"], DossierStatus["label"]>;

export interface ApplicationStatus {
  application_version: string;
  phase: "foundation" | "ledger" | "operations" | "assets";
  database: {
    status: "ready" | "not_ready";
    schema_revision: string | null;
    expected_revision: string;
  };
  fiscal: { status: "research_only"; available_vintages: string[] };
  storage_warning?: string | null;
  dossier?: DossierStatus | null;
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isDossierStatus(value: unknown): value is DossierStatus {
  if (!record(value)) return false;
  const status = value.status;
  if (
    status !== "incomplet"
    && status !== "bloque"
    && status !== "pret_a_verifier"
    && status !== "cloture"
  ) return false;
  if (value.label !== DOSSIER_LABELS[status]) return false;
  if (value.vintage_status !== "research_only") return false;
  if (typeof value.label === "string" && /declarable|déclarable/i.test(value.label)) return false;
  const yearStatus = value.year_status;
  if (
    yearStatus !== null
    && yearStatus !== "OPEN"
    && yearStatus !== "READY_TO_CLOSE"
    && yearStatus !== "CLOSED"
  ) return false;
  if (!(value.fiscal_year_id === null || typeof value.fiscal_year_id === "number")) return false;
  if (!(value.year === null || typeof value.year === "number")) return false;
  return true;
}

export function isApplicationStatus(value: unknown): value is ApplicationStatus {
  if (!record(value) || !record(value.database) || !record(value.fiscal)) return false;
  const dossier = value.dossier;
  return typeof value.application_version === "string"
    && (value.phase === "foundation" || value.phase === "ledger" || value.phase === "operations" || value.phase === "assets")
    && ["ready", "not_ready"].includes(String(value.database.status))
    && (typeof value.database.schema_revision === "string" || value.database.schema_revision === null)
    && typeof value.database.expected_revision === "string"
    && value.fiscal.status === "research_only"
    && Array.isArray(value.fiscal.available_vintages)
    && value.fiscal.available_vintages.every((v: unknown) => typeof v === "string")
    && (dossier === undefined || dossier === null || isDossierStatus(dossier));
}

export async function fetchStatus(signal: AbortSignal): Promise<ApplicationStatus> {
  const response = await fetch("/api/status", {
    signal, cache: "no-store", headers: { Accept: "application/json" },
  });
  if (response.status !== 200 && response.status !== 503) {
    throw new Error("Le service ne répond pas correctement.");
  }
  const body: unknown = await response.json();
  if (!isApplicationStatus(body)) throw new Error("La réponse du service est inattendue.");
  if (response.status === 503 && body.database.status === "ready") {
    throw new Error("L’état du service est incohérent.");
  }
  return body;
}
