import { isDossierStatus, type DossierStatus } from "../api/status";
import type { ScreenPhase } from "./screenState";

export const DOSSIER_HINTS: Record<DossierStatus["status"], string> = {
  incomplet: "Il manque encore des éléments avant de vérifier ce dossier.",
  bloque: "Une sortie est bloquée. Le détail est dans Fiscalité LMNP.",
  pret_a_verifier: "À vérifier avant clôture. Ce dossier n’est pas une déclaration.",
  cloture: "Exercice clôturé. Les millésimes restent en recherche.",
};

/** Affirmative statuses exist only for a successful, current read. */
export function showsDossierIndicator(
  phase: ScreenPhase,
  databaseReady: boolean,
  dossier: unknown,
): dossier is DossierStatus {
  return phase === "loaded" && databaseReady && isDossierStatus(dossier);
}

export function showsOperationalStorage(phase: ScreenPhase, databaseReady: boolean): boolean {
  return phase === "loaded" && databaseReady;
}
