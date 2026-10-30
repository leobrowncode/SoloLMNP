import { useEffect, type Ref } from "react";
import { Link } from "react-router-dom";
import type { ApiErrorDetail } from "../api/errors";
import { importIssueLines } from "../api/errors";

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
  return (
    <div role="alert" className={className} tabIndex={-1} ref={alertRef}>
      <p>{detail.message}</p>
      {otherIssues.length > 1 && (
        <ul>
          {otherIssues.map((issue) => (
            <li key={`${issue.code}-${issue.message}`}>{issue.message}</li>
          ))}
        </ul>
      )}
      {importLines.length > 0 && (
        <ul className="import-error-lines">
          {importLines.map((issue) => (
            <li key={`${issue.code}-${issue.line}-${issue.message}`}>
              Ligne {issue.line} : {issue.message}
            </li>
          ))}
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
