import { createContext } from "react";
import type { BuildResponse, DossierMap, GrilleLigne, MouvementLigne } from "../lib/api";

export type SessionV1 = {
  chemin: string;
  dossier: DossierMap;
  mouvements: MouvementLigne[];
  grille: GrilleLigne[];
  calcul: BuildResponse | null;
};

export type DossierStore = {
  session: SessionV1 | null;
  setSession: (value: SessionV1 | null) => void;
  mergeDossier: (patch: DossierMap) => void;
  setMouvements: (lignes: MouvementLigne[]) => void;
  setCalcul: (calcul: BuildResponse | null) => void;
};

export const STORAGE_KEY = "sololmnp-v1-chemin";

export const DossierCtx = createContext<DossierStore | null>(null);
