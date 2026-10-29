import { useContext, useEffect, useMemo } from "react";
import { UnsavedContext } from "./unsavedContext";

/** Enregistre une saisie en cours pour bloquer la navigation et l’actualisation. */
export function useUnsavedGuard(active: boolean) {
  const ctx = useContext(UnsavedContext);
  const id = useMemo(() => Symbol("unsaved"), []);
  useEffect(() => {
    if (!ctx || !active) return;
    return ctx.register(id);
  }, [active, ctx, id]);
}
