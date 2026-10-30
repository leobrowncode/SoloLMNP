import { useEffect, useEffectEvent, useState } from "react";
import type { ApiErrorDetail } from "../api/errors";
import {
  beginLoad, defer, failLoad, finishLoad, idleView, toApiError, type ScreenView,
} from "./screenState";

export function useScreenQuery<T>(
  load: (signal: AbortSignal) => Promise<T>,
  key: string,
  options?: {
    enabled?: boolean;
    keepPrevious?: boolean;
    isEmpty?: (data: T) => boolean;
    mapError?: (reason: unknown) => ApiErrorDetail;
  },
): { state: ScreenView<T>; retry: () => void } {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<ScreenView<T>>(() => beginLoad(idleView<T>(), false));
  const loadEvent = useEffectEvent((signal: AbortSignal) => load(signal));
  const readOptions = useEffectEvent(() => options);

  function retry() {
    const keep = options?.keepPrevious ?? false;
    setState((current) => beginLoad(current, keep && current.data !== null));
    setAttempt((value) => value + 1);
  }

  useEffect(() => {
    const controller = new AbortController();
    const currentOptions = readOptions();
    if (currentOptions?.enabled === false) {
      defer(() => {
        if (!controller.signal.aborted) setState(idleView());
      });
      return () => controller.abort();
    }
    const keep = currentOptions?.keepPrevious ?? false;
    defer(() => {
      if (controller.signal.aborted) return;
      setState((current) => beginLoad(current, keep && current.data !== null));
    });
    void loadEvent(controller.signal).then(
      (data) => {
        if (controller.signal.aborted) return;
        setState(finishLoad(data, readOptions()?.isEmpty));
      },
      (reason: unknown) => {
        if (controller.signal.aborted) return;
        const latest = readOptions();
        const detail = latest?.mapError?.(reason) ?? toApiError(reason);
        setState((current) => failLoad(
          current,
          detail,
          (latest?.keepPrevious ?? false) && current.data !== null,
        ));
      },
    );
    return () => controller.abort();
  }, [attempt, key]);

  return { state, retry };
}
