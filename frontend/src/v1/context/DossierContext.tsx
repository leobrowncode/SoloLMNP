import { useCallback, useMemo, useState, type ReactNode } from "react";
import type { BuildResponse, DossierMap, MouvementLigne } from "../lib/api";
import { DossierCtx, STORAGE_KEY, type DossierStore, type SessionV1 } from "./dossierStore";

export function DossierProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<SessionV1 | null>(null);

  const setSession = useCallback((value: SessionV1 | null) => {
    setSessionState(value);
    if (value?.chemin) sessionStorage.setItem(STORAGE_KEY, value.chemin);
    if (!value) sessionStorage.removeItem(STORAGE_KEY);
  }, []);

  const mergeDossier = useCallback((patch: DossierMap) => {
    setSessionState((courant) => {
      if (!courant) return courant;
      return { ...courant, dossier: { ...courant.dossier, ...patch } };
    });
  }, []);

  const setMouvements = useCallback((lignes: MouvementLigne[]) => {
    setSessionState((courant) => (courant ? { ...courant, mouvements: lignes } : courant));
  }, []);

  const setCalcul = useCallback((calcul: BuildResponse | null) => {
    setSessionState((courant) => (courant ? { ...courant, calcul } : courant));
  }, []);

  const value = useMemo<DossierStore>(
    () => ({ session, setSession, mergeDossier, setMouvements, setCalcul }),
    [session, setSession, mergeDossier, setMouvements, setCalcul],
  );

  return <DossierCtx.Provider value={value}>{children}</DossierCtx.Provider>;
}
