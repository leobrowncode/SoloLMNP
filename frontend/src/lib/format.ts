/**
 * French display and exact money parsing.
 *
 * Amounts are integer cents (bigint). Display uses Intl.NumberFormat("fr-FR")
 * without passing the amount through a binary float. The value kept in form
 * state until submit is the typed text; the API payload stays the exact
 * decimal string from centsToApiAmount ("1234.56"). The backend stores that
 * as integer cents. Nothing here changes accounting semantics.
 */
import { GLOSSARY } from "../features/glossary";

export const AMOUNT_INPUT_ERROR = "Indiquez un montant en euros, par exemple 1 234,56.";
export const DATE_HINT = "Format JJ/MM/AAAA.";

const CURRENCY = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const PLAIN = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function groupInteger(digits: string, separator: string): string {
  const parts: string[] = [];
  for (let index = digits.length; index > 0; index -= 3) {
    parts.unshift(digits.slice(Math.max(0, index - 3), index));
  }
  return parts.join(separator);
}

function formatWith(formatter: Intl.NumberFormat, cents: bigint): string {
  const negative = cents < 0n;
  const absolute = negative ? -cents : cents;
  const whole = (absolute / 100n).toString();
  const fraction = (absolute % 100n).toString().padStart(2, "0");
  const sample = formatter.formatToParts(negative ? -1234.5 : 1234.5);
  const group = sample.find((part) => part.type === "group")?.value ?? "\u202f";
  const decimal = sample.find((part) => part.type === "decimal")?.value ?? ",";
  const grouped = groupInteger(whole, group);
  let emitted = false;
  let out = "";
  for (const part of sample) {
    if (part.type === "minusSign") {
      if (negative) out += part.value;
      continue;
    }
    if (part.type === "integer" || part.type === "group") {
      if (!emitted) {
        out += grouped;
        emitted = true;
      }
      continue;
    }
    if (part.type === "decimal") {
      out += decimal;
      continue;
    }
    if (part.type === "fraction") {
      out += fraction;
      continue;
    }
    out += part.value;
  }
  return out;
}

/** "1 234,56 €" from integer cents, including the French currency spacing. */
export function formatCents(cents: bigint): string {
  return formatWith(CURRENCY, cents);
}

/** "1 234,56" from integer cents, without the euro sign. */
export function formatAmountFromCents(cents: bigint): string {
  return formatWith(PLAIN, cents);
}

/**
 * Parse a typed or API amount to exact cents.
 * Accepts "1 234,56", "1.234,56", "1234.56", "1234,5" and an optional leading minus.
 */
export function parseAmountToCents(input: string): bigint {
  const trimmed = input.trim();
  if (!trimmed || /[eE]/.test(trimmed)) throw new Error(AMOUNT_INPUT_ERROR);
  let sign = 1n;
  let body = trimmed;
  if (body.startsWith("+")) body = body.slice(1).trim();
  else if (body.startsWith("-") || body.startsWith("−")) {
    sign = -1n;
    body = body.slice(1).trim();
  }
  body = body.replace(/€/g, "").replace(/\beur\b/gi, "").trim();
  body = body.replace(/[\s\u00a0\u202f\u2009\u2007]+/g, "");
  const commas = body.match(/,/g)?.length ?? 0;
  const dots = body.match(/\./g)?.length ?? 0;
  const lastComma = body.lastIndexOf(",");
  const lastDot = body.lastIndexOf(".");
  if (lastComma >= 0 && lastDot >= 0) {
    body = lastComma > lastDot
      ? body.replace(/\./g, "").replace(",", ".")
      : body.replace(/,/g, "");
  } else if (lastComma >= 0) {
    if (commas > 1) throw new Error(AMOUNT_INPUT_ERROR);
    body = body.replace(",", ".");
  } else if (dots > 1) {
    throw new Error(AMOUNT_INPUT_ERROR);
  }
  if (!/^\d+(?:\.\d{1,2})?$/.test(body)) throw new Error(AMOUNT_INPUT_ERROR);
  const [whole = "0", fraction = ""] = body.split(".");
  return sign * (BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0")));
}

/** Canonical API decimal. The backend stores the same number as integer cents. */
export function centsToApiAmount(value: bigint): string {
  const sign = value < 0n ? "-" : "";
  const absolute = value < 0n ? -value : value;
  return `${sign}${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
}

/** French currency from an API decimal or a typed amount. Unknown text is returned unchanged. */
export function formatEuros(value: string): string {
  try {
    return formatCents(parseAmountToCents(value));
  } catch {
    return value;
  }
}

/** French number from an API decimal, without repeating the euro sign of a column header. */
export function formatAmount(value: string): string {
  try {
    return formatAmountFromCents(parseAmountToCents(value));
  } catch {
    return value;
  }
}

/** ISO date (AAAA-MM-JJ) shown as JJ/MM/AAAA. Other text is left unchanged. */
export function formatIsoDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value.trim());
  if (!match) return value;
  const [, year, month, day] = match;
  return `${day}/${month}/${year}`;
}

/** Date, optionally with HH:MM taken from the source string (conservation stamps). */
export function formatTimestamp(value: string): string {
  const date = formatIsoDate(value.slice(0, 10));
  if (!/^\d{2}\/\d{2}\/\d{4}$/.test(date)) return value;
  const time = value.length >= 16 ? value.slice(11, 16) : "";
  return time ? `${date} ${time}` : date;
}

const CLOCK = new Intl.DateTimeFormat("fr-FR", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** Local time as HH:MM, for example 15:42. Independent of the locale's hour separator. */
export function formatClockTime(value: Date): string {
  const parts = CLOCK.formatToParts(value);
  const hour = parts.find((part) => part.type === "hour")?.value ?? "";
  const minute = parts.find((part) => part.type === "minute")?.value ?? "";
  if (!hour || !minute) return CLOCK.format(value);
  return `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
}

export const ENUM_LABELS = {
  accountType: {
    ASSET: "Actif",
    LIABILITY: "Dette",
    EQUITY: "Capitaux",
    EXPENSE: "Charge",
    INCOME: "Produit",
  },
  assetCategory: {
    LAND: "Terrain",
    BUILDING: "Construction",
    FURNITURE: "Mobilier",
    EQUIPMENT: "Équipement",
    IMPROVEMENT: "Travaux immobilisés",
    OTHER: "Autre immobilisation",
  },
  planKind: {
    LAND: "Terrain",
    BUILDING: "Construction",
    COMPONENT: "Composant",
  },
  depreciationMethod: {
    NONE: "Aucune",
    LINEAR: "Linéaire",
  },
  yearStatus: {
    OPEN: "ouvert",
    CLOSED: "clôturé",
    READY_TO_CLOSE: "prêt à clôturer",
  },
  entryStatus: {
    DRAFT: "Brouillon",
    VALIDATED: "Validée",
  },
  entrySource: {
    MANUAL: "Saisie manuelle",
    REVERSAL: "Extourne",
    REVENUE: "Recettes",
    EXPENSE: "Dépenses",
    SETTLEMENT: "Règlements",
    LOAN_PAYMENT: "Échéances d’emprunt",
    LOAN_FUNDING: "Déblocages d’emprunt",
    DEPRECIATION: "Dotations aux amortissements",
    OPENING: GLOSSARY["a-nouveaux"].label,
    INVENTORY: `${GLOSSARY.inventaire.label} manuel`,
  },
  operationKind: {
    REVENUE: "Recette",
    EXPENSE: "Dépense",
    SETTLEMENT: "Règlement",
    LOAN_PAYMENT: "Échéance",
    LOAN_FUNDING: "Déblocage",
  },
  fiscalTreatment: {
    REQUIRES_REVIEW: "À vérifier",
    DEDUCTIBLE: "Déductible",
    PARTIAL: "Partiellement déductible",
    NON_DEDUCTIBLE: "Non déductible",
  },
  periodStatus: {
    CALCULATED: "Calculée",
    POSTED: "Comptabilisée",
  },
  operationStatus: {
    POSTED: "Comptabilisée",
    REVERSED: "Extournée",
  },
  importStatus: {
    valid: "Valide",
    duplicate: "Doublon",
    warning: "Avertissement",
    error: "Erreur",
  },
  worksheetLevel: {
    info: "Information",
    warning: "Avertissement",
    error: "Erreur",
  },
} as const;

export type EnumGroup = keyof typeof ENUM_LABELS;

/** French label for a visible enum. An unknown code stays visible as sent by the API. */
export function enumLabel(group: EnumGroup, code: string): string {
  const labels: Record<string, string> = ENUM_LABELS[group];
  return labels[code] ?? code;
}

export function enumChoices(group: EnumGroup): [string, string][] {
  return Object.entries(ENUM_LABELS[group]);
}
