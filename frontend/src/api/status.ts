export interface ApplicationStatus {
  application_version: string;
  phase: "foundation" | "ledger";
  database: {
    status: "ready" | "not_ready";
    schema_revision: string | null;
    expected_revision: string;
  };
  fiscal: { status: "research_only"; available_vintages: string[] };
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isApplicationStatus(value: unknown): value is ApplicationStatus {
  if (!record(value) || !record(value.database) || !record(value.fiscal)) return false;
  return typeof value.application_version === "string"
    && (value.phase === "foundation" || value.phase === "ledger")
    && ["ready", "not_ready"].includes(String(value.database.status))
    && (typeof value.database.schema_revision === "string" || value.database.schema_revision === null)
    && typeof value.database.expected_revision === "string"
    && value.fiscal.status === "research_only"
    && Array.isArray(value.fiscal.available_vintages)
    && value.fiscal.available_vintages.every((v: unknown) => typeof v === "string");
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
