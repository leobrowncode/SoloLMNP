import { isGlossaryId, type GlossaryId } from "../features/glossary";

export interface ApiErrorAction {
  label: string;
  href: string;
}

export interface ApiErrorIssue {
  code: string;
  message: string;
  field?: string;
  location?: string;
  line?: number;
  /** Glossary id. Unknown values are dropped. */
  help?: string;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  field?: string;
  location?: string;
  line?: number;
  action?: ApiErrorAction;
  issues?: ApiErrorIssue[];
  /** Glossary id. Unknown values are dropped. */
  help?: string;
}

/**
 * Codes that point at a glossary entry when the payload omits `help`.
 * Keep in sync with HELP_IDS in backend/app/core/api_errors.py.
 */
export const ERROR_HELP = {
  ALREADY_MATCHED: "rapprochement",
  ALREADY_REVERSED: "extourne",
  BANK_MATCH_EXISTS: "rapprochement",
  BUSINESS_REVERSAL_REQUIRED: "extourne",
  CLOSE_BLOCKED: "cloture",
  DEPRECIATION_TARGET_NOT_FOUND: "amortissement",
  EMPTY_OPENING: "a-nouveaux",
  EXPORT_BLOCKED: "liasse",
  FEC_INVALID: "fec",
  FISCAL_NOT_COMPUTED: "resultat-fiscal",
  LOAN_ACCOUNT_EXHAUSTED: "compte-164",
  LOAN_NOT_FUNDED: "compte-164",
  LOAN_OPENING_BALANCE: "emprunt",
  MAPPING_MISSING: "millesime",
  MAPPING_UNUSABLE: "millesime",
  MATCH_INCONSISTENT: "rapprochement",
  NOT_MATCHED: "rapprochement",
  NOT_VALIDATED: "extourne",
  OPENING_ALREADY_EXISTS: "a-nouveaux",
  OPENING_AUDIT_MISSING: "a-nouveaux",
  OPENING_JOURNAL_REQUIRED: "a-nouveaux",
  OPENING_TOO_LARGE: "a-nouveaux",
  PREVIOUS_YEAR_REQUIRED: "a-nouveaux",
  PRINCIPAL_EXCEEDED: "compte-164",
  RESULT_ACCOUNT_REQUIRED: "compte-120-129",
  REVERSAL_CHAIN: "extourne",
  REVERSAL_DATE: "extourne",
  SCHEDULE_NOT_FOUND: "amortissement",
  SETTLEMENTS_EXIST: "extourne",
  SIREN_MANQUANT: "siren",
  SIREN_REQUIRED: "siren",
  SOURCE_NOT_CLOSED: "a-nouveaux",
  TARGET_HAS_ENTRIES: "a-nouveaux",
  UNBALANCED_OPENING: "a-nouveaux",
  UNKNOWN_VINTAGE: "millesime",
  VINTAGE_NOT_USABLE: "millesime",
  WARNINGS_UNACKNOWLEDGED: "pre-controle",
  YEAR_NOT_CLOSED: "cloture",
} as const satisfies Record<string, GlossaryId>;

export function knownHelp(value: unknown): GlossaryId | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return isGlossaryId(trimmed) ? trimmed : undefined;
}

/** Explicit `help` wins. Otherwise a known code may point at the glossary. */
export function helpForError(detail: ApiErrorDetail): GlossaryId | null {
  const explicit = knownHelp(detail.help);
  if (explicit) return explicit;
  if (detail.code in ERROR_HELP) return ERROR_HELP[detail.code as keyof typeof ERROR_HELP];
  return null;
}

type RawDetail =
  | ApiErrorDetail
  | string
  | Array<{ msg?: string; type?: string; loc?: Array<string | number> } | string>;

function issueFromUnknown(item: unknown): ApiErrorIssue | null {
  if (typeof item === "string" && item.trim()) {
    return { code: "invalid", message: item.trim(), location: "body" };
  }
  if (!item || typeof item !== "object") return null;
  const record = item as Record<string, unknown>;
  const message = typeof record.msg === "string"
    ? record.msg
    : typeof record.message === "string"
      ? record.message
      : "";
  if (!message.trim()) return null;
  const loc = Array.isArray(record.loc) ? record.loc.map(String) : [];
  const field = loc.length > 1
    ? loc.slice(1).join(".")
    : typeof record.field === "string"
      ? record.field
      : null;
  const line = typeof record.line === "number" ? record.line : null;
  const help = knownHelp(record.help);
  return {
    code: typeof record.type === "string" ? record.type : typeof record.code === "string" ? record.code : "invalid",
    message,
    location: loc[0] ?? (typeof record.location === "string" ? record.location : "body"),
    ...(field ? { field } : {}),
    ...(line !== null ? { line } : {}),
    ...(help ? { help } : {}),
  };
}

function withHelp<T extends { help?: string }>(item: T): T {
  const help = knownHelp(item.help);
  const copy: T = { ...item };
  delete copy.help;
  return help ? { ...copy, help } : copy;
}

export function parseApiErrorDetail(detail: RawDetail | undefined): ApiErrorDetail {
  if (typeof detail === "string" && detail.trim()) {
    return { code: "HTTP_ERROR", message: detail.trim() };
  }
  if (Array.isArray(detail)) {
    const issues = detail.map(issueFromUnknown).filter((item): item is ApiErrorIssue => item !== null);
    return {
      code: "VALIDATION_ERROR",
      message: issues.map((item) => item.message).join(" ") || "Les données envoyées sont invalides.",
      issues,
    };
  }
  if (detail && typeof detail === "object") {
    const record = detail as ApiErrorDetail;
    const message = record.message?.trim()
      || "Opération refusée. Vérifiez les champs, les dates et les montants au centime.";
    const help = knownHelp(record.help);
    return {
      code: record.code || "HTTP_ERROR",
      message,
      ...(record.field ? { field: record.field } : {}),
      ...(record.location ? { location: record.location } : {}),
      ...(record.line !== undefined ? { line: record.line } : {}),
      ...(record.action ? { action: record.action } : {}),
      ...(record.issues ? { issues: record.issues.map((issue) => withHelp(issue)) } : {}),
      ...(help ? { help } : {}),
    };
  }
  return {
    code: "HTTP_ERROR",
    message: "Opération refusée. Vérifiez les champs, les dates et les montants au centime.",
  };
}

/** Map API field paths to form control names used in ReviewForm. */
export function formFieldName(apiField: string | undefined): string | null {
  if (!apiField) return null;
  return apiField.split(".").pop() ?? apiField;
}

export function issuesForForm(issues: ApiErrorIssue[] | undefined, formFields: Set<string>): ApiErrorIssue[] {
  if (!issues?.length) return [];
  return issues.filter((issue) => {
    const name = formFieldName(issue.field);
    return name ? formFields.has(name) : false;
  });
}

export function importIssueLines(detail: ApiErrorDetail): ApiErrorIssue[] {
  if (detail.line !== undefined) {
    return [{ code: detail.code, message: detail.message, line: detail.line, location: detail.location ?? "import" }];
  }
  return (detail.issues ?? []).filter((issue) => issue.line !== undefined);
}

export function errorSummary(detail: ApiErrorDetail): string {
  if (detail.issues?.length) {
    const fieldIssues = detail.issues.filter((issue) => issue.field);
    if (fieldIssues.length) return fieldIssues.map((issue) => issue.message).join(" ");
  }
  return detail.message;
}
