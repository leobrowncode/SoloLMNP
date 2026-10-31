import { centsToApiAmount, formatEuros, parseAmountToCents } from "../lib/format";

/** Texts that show up on at least two rows. Each is rendered once, above the rows. */
export function repeatedTexts(values: Array<string | null | undefined>): string[] {
  const counts = new Map<string, number>();
  for (const value of values) {
    const text = value?.trim() ?? "";
    if (!text) continue;
    counts.set(text, (counts.get(text) ?? 0) + 1);
  }
  return [...counts.entries()].filter(([, count]) => count >= 2).map(([text]) => text);
}

export function isSharedText(value: string | null | undefined, shared: readonly string[]): boolean {
  const text = value?.trim() ?? "";
  return text.length > 0 && shared.includes(text);
}

export function postedTotalCents(
  periods: readonly { id: number; amount: string }[],
  items: readonly { period_id: number; status: string }[],
): bigint {
  const posted = new Set(
    items.filter((item) => item.status === "posted").map((item) => item.period_id),
  );
  return periods.reduce(
    (sum, period) => (posted.has(period.id) ? sum + parseAmountToCents(period.amount) : sum),
    0n,
  );
}

/** One sentence: count, total, and whether the batch was a replay. */
export function depreciationPostedSentence(count: number, totalCents: bigint, replayed: boolean): string {
  const plural = count > 1;
  const noun = plural ? "dotations" : "dotation";
  const verb = replayed
    ? (plural ? "déjà comptabilisées, sans doublon" : "déjà comptabilisée, sans doublon")
    : (plural ? "comptabilisées" : "comptabilisée");
  return `${count} ${noun} ${verb}, total ${formatEuros(centsToApiAmount(totalCents))}.`;
}
