import { parseApiErrorDetail, type ApiErrorDetail } from "./errors";
import { RequestError } from "./ledger";
import { isDossierStatus, type DossierStatus } from "./status";

export const DASHBOARD_STEPS = [
  "structure",
  "operations",
  "assets",
  "opening",
  "closing",
  "filing",
] as const;

export type DashboardStepId = (typeof DASHBOARD_STEPS)[number];

export const DASHBOARD_STATUS_LABELS = {
  a_faire: "À faire",
  en_cours: "En cours",
  bloque: "Bloquée",
  pret: "Prête",
  fait: "Faite",
} as const;

export type DashboardStepStatus = keyof typeof DASHBOARD_STATUS_LABELS;

export interface DashboardAction {
  label: string;
  href: string;
}

export interface DashboardPrerequisite {
  code: string;
  message: string;
  action: DashboardAction;
}

export interface DashboardEvent {
  occurred_at: string;
  label: string;
}

export interface DashboardStep {
  id: DashboardStepId;
  label: string;
  status: DashboardStepStatus;
  status_label: (typeof DASHBOARD_STATUS_LABELS)[DashboardStepStatus];
  summary: string;
  prerequisites: DashboardPrerequisite[];
  last_event: DashboardEvent | null;
  amount_cents: number | null;
}

export interface DashboardContinue {
  label: "Continuer";
  href: string;
  detail: string;
  step: DashboardStepId;
}

export interface DashboardPayload {
  dossier: DossierStatus;
  continue: DashboardContinue;
  steps: DashboardStep[];
}

const FORBIDDEN = /declarable|déclarable/i;

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isHref(value: unknown): value is string {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//");
}

function isAction(value: unknown): value is DashboardAction {
  if (!record(value) || typeof value.label !== "string" || !value.label.trim()) return false;
  if (FORBIDDEN.test(value.label)) return false;
  return isHref(value.href);
}

function isPrerequisite(value: unknown): value is DashboardPrerequisite {
  if (!record(value) || typeof value.code !== "string" || typeof value.message !== "string") return false;
  if (FORBIDDEN.test(value.code) || FORBIDDEN.test(value.message)) return false;
  return isAction(value.action);
}

function isEvent(value: unknown): value is DashboardEvent {
  if (!record(value) || typeof value.occurred_at !== "string" || typeof value.label !== "string") return false;
  if (!value.occurred_at.trim() || !value.label.trim()) return false;
  return !FORBIDDEN.test(value.label);
}

function isCents(value: unknown): value is number | null {
  if (value === null) return true;
  return typeof value === "number" && Number.isInteger(value);
}

function isStep(value: unknown, id: DashboardStepId): value is DashboardStep {
  if (!record(value) || value.id !== id) return false;
  const status = value.status;
  if (typeof status !== "string" || !(status in DASHBOARD_STATUS_LABELS)) return false;
  const code = status as DashboardStepStatus;
  if (typeof value.status_label !== "string" || value.status_label !== DASHBOARD_STATUS_LABELS[code]) return false;
  if (typeof value.label !== "string" || typeof value.summary !== "string") return false;
  if (FORBIDDEN.test(value.label) || FORBIDDEN.test(value.summary) || FORBIDDEN.test(value.status_label)) return false;
  if (!Array.isArray(value.prerequisites) || !value.prerequisites.every(isPrerequisite)) return false;
  if (!(value.last_event === null || isEvent(value.last_event))) return false;
  return isCents(value.amount_cents);
}

function isContinue(value: unknown): value is DashboardContinue {
  if (!record(value) || value.label !== "Continuer" || typeof value.detail !== "string") return false;
  if (FORBIDDEN.test(value.detail)) return false;
  if (!isHref(value.href)) return false;
  return DASHBOARD_STEPS.some((id) => id === value.step);
}

export function isDashboard(value: unknown): value is DashboardPayload {
  if (!record(value) || !isDossierStatus(value.dossier) || !isContinue(value.continue)) return false;
  const steps = value.steps;
  if (!Array.isArray(steps)) return false;
  if (steps.length === 0) return true;
  if (steps.length !== DASHBOARD_STEPS.length) return false;
  return DASHBOARD_STEPS.every((id, index) => isStep(steps[index], id));
}

export async function fetchDashboard(signal: AbortSignal): Promise<DashboardPayload> {
  const response = await fetch("/api/dashboard", {
    signal,
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const detail = record(body) ? body.detail : undefined;
    throw new RequestError(parseApiErrorDetail(detail as Parameters<typeof parseApiErrorDetail>[0]), response.status);
  }
  if (!isDashboard(body)) throw new Error("La réponse du dossier est inattendue.");
  return body;
}

export function dashboardFailure(reason: unknown): ApiErrorDetail {
  if (reason instanceof RequestError) return reason.detail;
  if (reason instanceof Error && reason.message.trim()) {
    return { code: "HTTP_ERROR", message: reason.message };
  }
  return { code: "HTTP_ERROR", message: "Le tableau de bord ne répond pas. Réessayez." };
}
