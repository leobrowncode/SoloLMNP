import { downloadFiling } from "../../api/download";
import { authHeaders, noteUnauthorized } from "../../api/session";

export type DossierMap = Record<string, unknown>;

export type MouvementLigne = {
  date: string;
  piece: string;
  libelle: string;
  compte: string;
  debit_centimes: number | string;
  credit_centimes: number | string;
};

export type GrilleLigne = {
  cle: string;
  libelle: string;
  ratio_dix_millieme: number | null;
  duree_mois: number;
  compte: string;
  compte_amortissement: string;
  base_centimes: number;
};

export type BuildResponse = {
  nom: string;
  siret: string;
  millesime: string;
  empreinte: string;
  etat: {
    demande: string;
    effectif: string;
    libelle: string;
    texte: string;
  };
  annees: Record<string, Record<string, number | boolean | Record<string, number>>>;
  sorties?: {
    efi: { lignes: EfiLigne[]; controles: { texte: string; ok: boolean }[] };
    traces: Record<string, TraceCase>;
    suivi: unknown;
    fec: { nom: string; valide: boolean; bloquantes: string[] };
    empreintes: Record<string, string>;
    archive_nom: string;
    archive_sha256: string;
  };
  erreur?: string;
};

export type EfiLigne = {
  ecran: string;
  formulaire: string;
  case: string;
  montant: string | null;
  comptes: string[];
  ecritures: string[];
  origine: string;
};

export type TraceCase = {
  comptes: string[];
  ecritures: string[];
  origine: string;
};

export type DossierPayload = {
  dossier: DossierMap;
  mouvements: MouvementLigne[];
  grille: GrilleLigne[];
  erreur?: string;
};

function entetes(json = false): Headers {
  const headers = authHeaders({ "X-SoloLMNP-Request": "1" });
  if (json) headers.set("Content-Type", "application/json");
  return headers;
}

async function lire<T>(response: Response): Promise<T> {
  if (response.status === 401 || response.status === 403) {
    noteUnauthorized(response.status);
  }
  const corps = (await response.json()) as T & { erreur?: string };
  if (!response.ok) {
    throw new Error(corps.erreur || "Réponse HTTP refusée.");
  }
  return corps;
}

export async function chargerModeles() {
  const response = await fetch("/api/v1/modeles", { headers: entetes(), cache: "no-store" });
  return lire<{ modeles: { id: string; etiquette: string }[] }>(response);
}

export async function chargerModele(id: string) {
  const response = await fetch(`/api/v1/modeles/${encodeURIComponent(id)}`, {
    headers: entetes(),
    cache: "no-store",
  });
  return lire<DossierPayload>(response);
}

export async function chargerDossier(): Promise<DossierPayload | null> {
  const response = await fetch("/api/v1/dossier", { headers: entetes(), cache: "no-store" });
  if (response.status === 404) return null;
  return lire<DossierPayload>(response);
}

export async function enregistrerDossier(dossier: DossierMap, mouvements?: MouvementLigne[]) {
  const response = await fetch("/api/v1/dossier", {
    method: "PUT",
    headers: entetes(true),
    body: JSON.stringify({ dossier, mouvements }),
  });
  return lire<DossierPayload>(response);
}

export async function creerDepuisModele(modele: string) {
  const response = await fetch("/api/v1/dossiers", {
    method: "POST",
    headers: entetes(true),
    body: JSON.stringify({ modele }),
  });
  return lire<DossierPayload>(response);
}

export async function construire() {
  const response = await fetch("/api/v1/build", {
    method: "POST",
    headers: entetes(true),
    body: JSON.stringify({}),
  });
  return lire<BuildResponse>(response);
}

export async function chargerCategories() {
  const response = await fetch("/api/v1/categories", { headers: entetes(), cache: "no-store" });
  return lire<{ categories: { id: string; libelle: string; compte: string; sens: string }[] }>(response);
}

export function telechargerSortie(nom: string) {
  return downloadFiling(`/api/v1/sorties/${encodeURIComponent(nom)}`);
}

export async function listerJustificatifs() {
  const response = await fetch("/api/v1/justificatifs", { headers: entetes(), cache: "no-store" });
  return lire<{ noms: string[] }>(response);
}

export async function deposerJustificatif(fichier: File) {
  const nom = fichier.name.replace(/[^A-Za-z0-9._-]/g, "-").replace(/^[-.]+/, "") || "piece.pdf";
  const response = await fetch(`/api/v1/justificatifs/${encodeURIComponent(nom)}`, {
    method: "PUT",
    headers: authHeaders({
      "X-SoloLMNP-Request": "1",
      "Content-Type": fichier.type || "application/octet-stream",
    }),
    body: fichier,
  });
  return lire<{ nom: string; erreur?: string }>(response);
}
