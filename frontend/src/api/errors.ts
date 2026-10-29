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
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  field?: string;
  location?: string;
  line?: number;
  action?: ApiErrorAction;
  issues?: ApiErrorIssue[];
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
  return {
    code: typeof record.type === "string" ? record.type : typeof record.code === "string" ? record.code : "invalid",
    message,
    location: loc[0] ?? (typeof record.location === "string" ? record.location : "body"),
    ...(field ? { field } : {}),
    ...(line !== null ? { line } : {}),
  };
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
    return {
      code: record.code || "HTTP_ERROR",
      message,
      ...(record.field ? { field: record.field } : {}),
      ...(record.location ? { location: record.location } : {}),
      ...(record.line !== undefined ? { line: record.line } : {}),
      ...(record.action ? { action: record.action } : {}),
      ...(record.issues ? { issues: record.issues.map((issue) => ({ ...issue })) } : {}),
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
