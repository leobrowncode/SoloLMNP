import { RequestError } from "../api/ledger";
import type { ApiErrorDetail } from "../api/errors";

export type ScreenPhase = "idle" | "loading" | "error" | "empty" | "loaded";

export interface ScreenView<T> {
  phase: ScreenPhase;
  data: T | null;
  error: ApiErrorDetail | null;
  /** True when a failed refresh kept the previous payload. */
  stale: boolean;
}

export const STALE_NOTICE = "Ces informations peuvent être périmées.";

export function idleView<T>(): ScreenView<T> {
  return { phase: "idle", data: null, error: null, stale: false };
}

export function emptyView<T>(): ScreenView<T> {
  return { phase: "empty", data: null, error: null, stale: false };
}

export function beginLoad<T>(current: ScreenView<T>, keepPrevious: boolean): ScreenView<T> {
  const data = keepPrevious ? current.data : null;
  return { phase: "loading", data, error: null, stale: data !== null };
}

export function finishLoad<T>(data: T, isEmpty?: (value: T) => boolean): ScreenView<T> {
  if (isEmpty?.(data)) return emptyView();
  return { phase: "loaded", data, error: null, stale: false };
}

export function failLoad<T>(
  current: ScreenView<T>,
  error: ApiErrorDetail,
  keepPrevious: boolean,
): ScreenView<T> {
  const data = keepPrevious ? current.data : null;
  return { phase: "error", data, error, stale: data !== null };
}

export function showsLoading<T>(state: ScreenView<T>): boolean {
  return state.phase === "loading" && state.data === null;
}

export function showsData<T>(state: ScreenView<T>): state is ScreenView<T> & { data: T } {
  return state.data !== null && (
    state.phase === "loaded" || state.phase === "loading" || state.phase === "error"
  );
}

/** Runs a view update after the effect body so it is not a synchronous setState. */
export function defer(update: () => void): void {
  queueMicrotask(update);
}

export function toApiError(reason: unknown, fallback = "Le service ne répond pas. Réessayez."): ApiErrorDetail {
  if (reason instanceof RequestError) return reason.detail;
  if (reason instanceof Error && reason.message.trim()) {
    return { code: "HTTP_ERROR", message: reason.message };
  }
  return { code: "HTTP_ERROR", message: fallback };
}
