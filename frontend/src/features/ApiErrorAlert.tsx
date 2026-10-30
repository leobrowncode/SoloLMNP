import { useEffect, type Ref } from "react";
import { Link } from "react-router-dom";
import { helpForError, importIssueLines, knownHelp, type ApiErrorDetail, type ApiErrorIssue } from "../api/errors";
import GlossaryTip from "./GlossaryTip";
import type { GlossaryId } from "./glossary";

function rejectionLabel(issue: ApiErrorIssue): string {
  if (issue.line === undefined) return issue.message;
  const place = issue.column
    ? `Ligne ${issue.line}, colonne ${issue.column}`
    : `Ligne ${issue.line}`;
  const value = issue.value ? ` Valeur « ${issue.value} ».` : issue.value === "" ? " Valeur vide." : "";
  const correction = issue.correction ? ` Correction attendue : ${issue.correction}` : "";
  return `${place} : ${issue.message}${value}${correction}`;
}

function issueHelp(issue: ApiErrorIssue, banner: GlossaryId | null): GlossaryId | null {
  const help = knownHelp(issue.help);
  if (!help || help === banner) return null;
  return help;
}

export default function ApiErrorAlert({
  detail,
  className = "ledger-error",
  onRetry,
  focus = false,
  alertRef,
}: {
  detail: ApiErrorDetail;
  className?: string;
  onRetry?: () => void;
  focus?: boolean;
  alertRef?: Ref<HTMLDivElement>;
}) {
  useEffect(() => {
    if (!focus || !alertRef || typeof alertRef === "function") return;
    alertRef.current?.focus();
  }, [alertRef, detail, focus]);
  const importLines = importIssueLines(detail);
  const otherIssues = (detail.issues ?? []).filter((issue) => issue.line === undefined);
  const bannerHelp = helpForError(detail);
  return (
    <div role="alert" className={className} tabIndex={-1} ref={alertRef}>
      <p>
        {detail.message}
        {bannerHelp && <GlossaryTip id={bannerHelp} />}
      </p>
      {otherIssues.length > 1 && (
        <ul>
          {otherIssues.map((issue) => {
            const help = issueHelp(issue, bannerHelp);
            return (
              <li key={`${issue.code}-${issue.message}`}>
                {issue.message}
                {help && <GlossaryTip id={help} />}
              </li>
            );
          })}
        </ul>
      )}
      {importLines.length > 0 && (
        <ul className="import-error-lines">
          {importLines.map((issue) => {
            const help = issueHelp(issue, bannerHelp);
            return (
              <li key={`${issue.code}-${issue.line}-${issue.message}`}>
                {rejectionLabel(issue)}
                {help && <GlossaryTip id={help} />}
              </li>
            );
          })}
        </ul>
      )}
      {(detail.action || onRetry) && (
        <p>
          {detail.action && <Link to={detail.action.href}>{detail.action.label}</Link>}
          {onRetry && <button type="button" onClick={onRetry}>Réessayer</button>}
        </p>
      )}
    </div>
  );
}
