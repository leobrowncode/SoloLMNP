import { useEffect, useRef, type ReactNode } from "react";
import ApiErrorAlert from "./ApiErrorAlert";
import { showsLoading, STALE_NOTICE, type ScreenView } from "./screenState";

export default function ScreenStatus<T>({
  state,
  onRetry,
  loading = null,
  empty = null,
  focusError = false,
  className,
}: {
  state: ScreenView<T>;
  onRetry?: () => void;
  loading?: ReactNode;
  empty?: ReactNode;
  focusError?: boolean;
  className?: string;
}) {
  const focusRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (focusError && state.phase === "error") focusRef.current?.focus();
  }, [focusError, state]);

  if (state.phase === "idle" || state.phase === "loaded") return null;
  if (state.phase === "loading") {
    if (!showsLoading(state) || loading == null) return null;
    return <div data-screen-phase="loading">{loading}</div>;
  }
  if (state.phase === "empty") {
    return <div data-screen-phase="empty">{empty}</div>;
  }
  return (
    <div data-screen-phase="error">
      {state.stale && <p className="notice screen-stale" role="status">{STALE_NOTICE}</p>}
      {state.error && (
        <ApiErrorAlert
          detail={state.error}
          focus={focusError}
          alertRef={focusRef}
          {...(onRetry ? { onRetry } : {})}
          {...(className ? { className } : {})}
        />
      )}
    </div>
  );
}
