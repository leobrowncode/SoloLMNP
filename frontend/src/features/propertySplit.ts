import { amount, cents } from "../api/ledger";
import { formatCents } from "../lib/format";

/**
 * Surface and price per square metre are local helpers. They only propose a
 * land/building split. The recorded values are the price, the costs, the land
 * and the building. The land stays outside the depreciable basis.
 */
export function proposeLandFromArea(
  draft: Record<string, string>,
  changed: string,
): Partial<Record<string, string>> {
  if (!["lot_m2", "price_m2", "acquisition_price"].includes(changed)) return {};
  const area = Number(String(draft.lot_m2 ?? "").replace(",", "."));
  if (!Number.isFinite(area) || area <= 0) return {};
  try {
    const pricePerMeter = cents(draft.price_m2 || "0");
    const price = cents(draft.acquisition_price || "0");
    if (pricePerMeter <= 0n || price <= 0n) return {};
    const land = BigInt(Math.round(area * Number(pricePerMeter)));
    if (land <= 0n || land >= price) return {};
    return { land_value: amount(land), building_value: amount(price - land) };
  } catch {
    return {};
  }
}

function readCents(value: string | undefined): bigint | null {
  const text = (value ?? "").trim();
  if (!text) return 0n;
  try {
    return cents(text);
  } catch {
    return null;
  }
}

/** One sentence when land + building does not equal the acquisition price. */
export function propertySplitGap(draft: Record<string, string>): string {
  if (!("acquisition_price" in draft) || !("land_value" in draft) || !("building_value" in draft)) {
    return "";
  }
  const price = readCents(draft.acquisition_price);
  const land = readCents(draft.land_value);
  const building = readCents(draft.building_value);
  if (price === null || land === null || building === null) return "";
  const sum = land + building;
  if (sum === price) return "";
  const gap = sum > price ? sum - price : price - sum;
  const side = sum > price ? "de plus" : "de moins";
  return (
    `Le terrain et le bâtiment totalisent ${formatCents(sum)}, `
    + `soit ${formatCents(gap)} ${side} que le prix d’acquisition (${formatCents(price)}).`
  );
}
