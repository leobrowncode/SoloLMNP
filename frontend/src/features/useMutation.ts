import { useCallback, useRef, useState } from "react";

export interface MutationController {
  /** True from the click until the request settles. A second call is ignored. */
  busy: boolean;
  /** Current step of a long action, or null once it has settled. */
  step: string | null;
  run: <T>(
    task: (report: (step: string) => void) => Promise<T>,
    initialStep?: string,
  ) => Promise<T | undefined>;
}

/**
 * One lock for every mutation on a screen.
 * The ref closes the double-click window before React disables the button.
 */
export function useMutation(): MutationController {
  const lock = useRef(false);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<string | null>(null);

  const run = useCallback(<T>(
    task: (report: (step: string) => void) => Promise<T>,
    initialStep = "Opération en cours…",
  ): Promise<T | undefined> => {
    if (lock.current) return Promise.resolve(undefined);
    lock.current = true;
    setBusy(true);
    setStep(initialStep);
    return task((next) => setStep(next)).finally(() => {
      lock.current = false;
      setBusy(false);
      setStep(null);
    });
  }, []);

  return { busy, step, run };
}
