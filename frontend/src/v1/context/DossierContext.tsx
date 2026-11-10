import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { BuildResponse, DossierMap, GrilleLigne, MouvementLigne } from "../lib/api";

export type SessionV1 = {
  chemin: string;
  dossier: DossierMap;
  mouvements: MouvementLigne[];
  grille: GrilleLigne[];
  calcul: BuildResponse | null;
};

type Store = {
  session: SessionV1 | null;
  setSession: (value: SessionV1 | null) => void;
  mergeDossier: (patch: DossierMap) => void;
  setMouvements: (lignes: MouvementLigne[]) => void;
  setCalcul: (calcul: BuildResponse | null) => void;
};

const Ctx = createContext<Store | null>(null);
const STORAGE_KEY = "sololmnp-v1-chemin";

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

  const value = useMemo(
    () => ({ session, setSession, mergeDossier, setMouvements, setCalcul }),
    [session, setSession, mergeDossier, setMouvements, setCalcul],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useDossierSession() {
  const store = useContext(Ctx);
  if (!store) throw new Error("DossierProvider manquant.");
  return store;
}

export function cheminMemorise(): string | null {
  return sessionStorage.getItem(STORAGE_KEY);
}
