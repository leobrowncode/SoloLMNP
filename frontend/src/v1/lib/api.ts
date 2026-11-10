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

async function lire<T>(response: Response): Promise<T> {
  const corps = (await response.json()) as T & { erreur?: string };
  if (!response.ok) {
    throw new Error("Réponse HTTP refusée.");
  }
  return corps;
}

export async function chargerModeles() {
  const response = await fetch("/api/v1/modeles");
  return lire<{ modeles: { id: string; chemin: string; etiquette: string }[] }>(response);
}

export async function chargerDossier(chemin: string) {
  const response = await fetch(`/api/v1/dossier?chemin=${encodeURIComponent(chemin)}`);
  return lire<{
    chemin: string;
    dossier: DossierMap;
    mouvements: MouvementLigne[];
    grille: GrilleLigne[];
    erreur?: string;
  }>(response);
}

export async function enregistrerDossier(chemin: string, dossier: DossierMap, mouvements?: MouvementLigne[]) {
  const response = await fetch("/api/v1/dossier", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chemin, dossier, mouvements }),
  });
  return lire<{ chemin: string; erreur?: string }>(response);
}

export async function creerDepuisModele(modele: string, nom: string) {
  const response = await fetch("/api/v1/dossiers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modele, nom }),
  });
  return lire<{ chemin: string; erreur?: string }>(response);
}

export async function construire(chemin: string) {
  const response = await fetch("/api/v1/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chemin }),
  });
  return lire<BuildResponse>(response);
}

export async function chargerCategories() {
  const response = await fetch("/api/v1/categories");
  return lire<{ categories: { id: string; libelle: string; compte: string; sens: string }[] }>(response);
}
