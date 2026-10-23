export type OperationKind = "REVENUE" | "EXPENSE";

export interface OperationType {
  code: string;
  label: string;
  account: string;
}

export const REVENUE_TYPES: OperationType[] = [
  { code: "LOY", label: "Loyer", account: "706000" },
  { code: "TROP", label: "Trop-perçu / régularisation", account: "706000" },
  { code: "CHG", label: "Charges locataires refacturées", account: "706000" },
  { code: "AUT", label: "Autre recette", account: "706000" },
];

export const EXPENSE_TYPES: OperationType[] = [
  { code: "ASS", label: "Assurance", account: "616000" },
  { code: "ENT", label: "Entretien / réparations", account: "615000" },
  { code: "FOU", label: "Fournitures", account: "606000" },
  { code: "HON", label: "Honoraires", account: "622000" },
  { code: "BAN", label: "Frais bancaires", account: "627000" },
  { code: "COP", label: "Copropriété", account: "614000" },
  { code: "FON", label: "Taxe foncière", account: "635000" },
  { code: "TAX", label: "Autres impôts et taxes", account: "635000" },
  { code: "GES", label: "Gestion locative", account: "622000" },
  { code: "INT", label: "Intérêts d’emprunt (si non saisis dans l’échéance)", account: "661000" },
  { code: "AUT", label: "Autre dépense", account: "606000" },
];

export function typesFor(kind: OperationKind): OperationType[] {
  return kind === "REVENUE" ? REVENUE_TYPES : EXPENSE_TYPES;
}

export function defaultType(kind: OperationKind): OperationType {
  return typesFor(kind)[0]!;
}

export function findType(kind: OperationKind, code: string): OperationType | undefined {
  return typesFor(kind).find((item) => item.code === code);
}

/** Strip accents and keep alphanumeric characters for a stable counterparty slug. */
export function slugifyParty(name: string): string {
  const normalized = name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Za-z0-9]+/g, "");
  return normalized.slice(0, 24) || "SANSNOM";
}

/** Build PREFIX-YYYY-MM-Party from type code, accounting date and counterparty. */
export function buildPieceReference(code: string, date: string, counterparty: string): string {
  const match = /^(\d{4})-(\d{2})/.exec(date.trim());
  const yearMonth = match ? `${match[1]}-${match[2]}` : "XXXX-XX";
  return `${code}-${yearMonth}-${slugifyParty(counterparty)}`;
}
