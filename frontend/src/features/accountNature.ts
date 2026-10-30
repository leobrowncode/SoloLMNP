/**
 * Accounting nature from the ledger API `account_type` enum
 * (ASSET, LIABILITY, EQUITY, EXPENSE, INCOME).
 * Usage (Activé / Inactif) is the separate `active` flag.
 * Labels come from the central enum map.
 */
import { ENUM_LABELS } from "../lib/format";

export const ACCOUNT_NATURES = ENUM_LABELS.accountType;

export type AccountType = keyof typeof ACCOUNT_NATURES;

export const ACCOUNT_TYPES = Object.keys(ACCOUNT_NATURES) as AccountType[];

export const USAGE_OPTIONS = [
  { value: "active", label: "Activé" },
  { value: "inactive", label: "Inactif" },
] as const;

export type UsageFilter = "" | (typeof USAGE_OPTIONS)[number]["value"];

export function isAccountType(value: string): value is AccountType {
  return Object.prototype.hasOwnProperty.call(ACCOUNT_NATURES, value);
}

/** Translated nature. An unknown enum value stays visible as sent by the API. */
export function accountNatureLabel(accountType: string): string {
  return isAccountType(accountType) ? ACCOUNT_NATURES[accountType] : accountType;
}

export function accountUsageLabel(active: boolean): "Activé" | "Inactif" {
  return active ? "Activé" : "Inactif";
}

export function matchesChartFilters(
  account: { account_type: string; active: boolean },
  nature: string,
  usage: UsageFilter,
): boolean {
  if (nature && account.account_type !== nature) return false;
  if (usage === "active" && !account.active) return false;
  if (usage === "inactive" && account.active) return false;
  return true;
}
