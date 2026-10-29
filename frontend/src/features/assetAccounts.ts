import type { Account } from "../api/ledger";

/** Mirrors backend/app/domain/assets/accounts.py. Longest prefix wins. */
const PREFIXES: readonly [string, string][] = [
  ["2135", "IMPROVEMENT"],
  ["2181", "IMPROVEMENT"],
  ["2182", "EQUIPMENT"],
  ["2183", "EQUIPMENT"],
  ["2184", "FURNITURE"],
  ["211", "LAND"],
  ["212", "BUILDING"],
  ["213", "BUILDING"],
  ["214", "BUILDING"],
  ["215", "EQUIPMENT"],
  ["218", "OTHER"],
];

export const DEFAULT_ASSET: Record<string, string | null> = {
  LAND: "211000",
  BUILDING: "213000",
  IMPROVEMENT: "213500",
  EQUIPMENT: "218300",
  FURNITURE: "218400",
  OTHER: null,
};

export function categoryOfAccount(number: string): string | null {
  let best: { length: number; category: string } | null = null;
  for (const [prefix, category] of PREFIXES) {
    if (number.startsWith(prefix) && (best === null || prefix.length > best.length)) {
      best = { length: prefix.length, category };
    }
  }
  return best?.category ?? null;
}

/** Same-length chart mirror: 213000 → 281300, 218400 → 281840. */
export function mirrorDepreciation(assetAccount: string): string | null {
  if (assetAccount.length < 4 || !assetAccount.startsWith("21")) return null;
  return `28${assetAccount.slice(1, -1)}`;
}

function option(account: Account): [string, string] {
  return [account.number, `${account.number} · ${account.label}`];
}

export function assetAccountChoices(accounts: Account[], category: string): [string, string][] {
  return accounts
    .filter((row) => row.active && categoryOfAccount(row.number) === category)
    .map(option);
}

export function componentAssetChoices(accounts: Account[]): [string, string][] {
  return accounts
    .filter((row) => {
      const category = categoryOfAccount(row.number);
      return row.active && (category === "BUILDING" || category === "IMPROVEMENT");
    })
    .map(option);
}

export function depreciationAccountChoices(accounts: Account[], assetAccount: string): [string, string][] {
  const mirror = mirrorDepreciation(assetAccount);
  if (!mirror) return [];
  return accounts.filter((row) => row.active && row.number === mirror).map(option);
}

export function preferredAccount(choices: [string, string][], preferred: string | null | undefined): string {
  if (preferred && choices.some(([value]) => value === preferred)) return preferred;
  return choices[0]?.[0] ?? "";
}

export function alignAssetDraft(
  accounts: Account[],
  draft: Record<string, string>,
  changed: string,
  scope: "asset" | "land" | "component",
): Partial<Record<string, string>> {
  if (scope === "component") {
    if (changed !== "asset_account") return {};
  } else if (changed !== "category" && changed !== "asset_account") {
    return {};
  }
  const category = scope === "land" ? "LAND" : draft.category ?? "";
  const assetChoices = scope === "component"
    ? componentAssetChoices(accounts)
    : assetAccountChoices(accounts, category);
  const currentAsset = draft.asset_account ?? "";
  const asset = assetChoices.some(([value]) => value === currentAsset)
    ? currentAsset
    : preferredAccount(assetChoices, scope === "component" ? null : DEFAULT_ASSET[category]);
  if (scope === "land") return asset === currentAsset ? {} : { asset_account: asset };
  const depreciationChoices = depreciationAccountChoices(accounts, asset);
  const currentDepreciation = draft.depreciation_account ?? "";
  const depreciation = depreciationChoices.some(([value]) => value === currentDepreciation)
    ? currentDepreciation
    : preferredAccount(depreciationChoices, mirrorDepreciation(asset));
  const patch: Partial<Record<string, string>> = {};
  if (asset !== currentAsset) patch.asset_account = asset;
  if (depreciation !== currentDepreciation) patch.depreciation_account = depreciation;
  return patch;
}
