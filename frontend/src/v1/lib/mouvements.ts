import type { MouvementLigne } from "./api";

export function parserCsvMouvements(texte: string): MouvementLigne[] {
  const lignes = texte
    .trim()
    .split(/\r?\n/)
    .filter((ligne) => ligne.trim().length > 0);
  if (lignes.length < 2) return [];
  const entete = lignes[0]?.split(",").map((cellule) => cellule.trim()) ?? [];
  const index = (nom: string) => entete.indexOf(nom);
  const idxDate = index("date");
  const idxPiece = index("piece");
  const idxLibelle = index("libelle");
  const idxCompte = index("compte");
  const idxDebit = index("debit_centimes");
  const idxCredit = index("credit_centimes");
  if (idxDate < 0 || idxCompte < 0) return [];
  return lignes.slice(1).map((ligne, ordre) => {
    const cellules = ligne.split(",");
    const debit = Number(cellules[idxDebit] ?? 0) || 0;
    const credit = Number(cellules[idxCredit] ?? 0) || 0;
    return {
      date: cellules[idxDate] ?? "",
      piece: cellules[idxPiece] ?? `IMPORT-${ordre + 1}`,
      libelle: cellules[idxLibelle] ?? "",
      compte: cellules[idxCompte] ?? "",
      debit_centimes: debit,
      credit_centimes: credit,
    };
  });
}

export function ligneDepuisCategorie(input: {
  categorieId: string;
  libelle: string;
  compte: string;
  sens: string;
  montantCentimes: number;
  date: string;
}): MouvementLigne | null {
  if (input.montantCentimes <= 0) return null;
  const base = {
    date: input.date,
    piece: `CAT-${input.categorieId.toUpperCase()}`,
    libelle: input.libelle,
    compte: input.compte,
    debit_centimes: 0,
    credit_centimes: 0,
  };
  if (input.sens === "credit") {
    return { ...base, credit_centimes: input.montantCentimes };
  }
  return { ...base, debit_centimes: input.montantCentimes };
}

export function totalParCompte(mouvements: MouvementLigne[], compte: string): number {
  return mouvements.reduce((total, ligne) => {
    if (ligne.compte !== compte) return total;
    const debit = Number(ligne.debit_centimes) || 0;
    const credit = Number(ligne.credit_centimes) || 0;
    return total + debit + credit;
  }, 0);
}
