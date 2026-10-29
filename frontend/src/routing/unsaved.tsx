import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useBlocker } from "react-router-dom";
import { UnsavedContext } from "./unsavedContext";

export function UnsavedChangesProvider({ children }: { children: ReactNode }) {
  const ids = useRef(new Set<symbol>());
  const [dirty, setDirty] = useState(false);

  const sync = useCallback(() => {
    setDirty(ids.current.size > 0);
  }, []);

  const register = useCallback((id: symbol) => {
    ids.current.add(id);
    sync();
    return () => {
      ids.current.delete(id);
      sync();
    };
  }, [sync]);

  const value = useMemo(() => ({ register }), [register]);
  const blocker = useBlocker(dirty);

  useEffect(() => {
    if (!dirty) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [dirty]);

  return (
    <UnsavedContext.Provider value={value}>
      {children}
      {blocker.state === "blocked" && (
        <div className="unsaved-dialog-backdrop" role="presentation">
          <div
            className="unsaved-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="unsaved-dialog-title"
            aria-describedby="unsaved-dialog-body"
          >
            <h2 id="unsaved-dialog-title">Quitter sans enregistrer ?</h2>
            <p id="unsaved-dialog-body">
              Des modifications n’ont pas été enregistrées. Si vous quittez maintenant, elles seront perdues.
            </p>
            <div className="form-actions">
              <button type="button" autoFocus onClick={() => blocker.reset()}>
                Rester sur la page
              </button>
              <button
                type="button"
                onClick={() => {
                  ids.current.clear();
                  sync();
                  blocker.proceed();
                }}
              >
                Quitter sans enregistrer
              </button>
            </div>
          </div>
        </div>
      )}
    </UnsavedContext.Provider>
  );
}
