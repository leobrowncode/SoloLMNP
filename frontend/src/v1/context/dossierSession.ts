import { useContext } from "react";
import { DossierCtx, STORAGE_KEY } from "./dossierStore";

export type { SessionV1 } from "./dossierStore";

export function useDossierSession() {
  const store = useContext(DossierCtx);
  if (!store) throw new Error("DossierProvider manquant.");
  return store;
}

export function cheminMemorise(): string | null {
  return sessionStorage.getItem(STORAGE_KEY);
}
