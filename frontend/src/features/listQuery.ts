export interface ListCriteria {
  search: string;
  status: string;
  category: string;
}

export const EMPTY_CRITERIA: ListCriteria = { search: "", status: "", category: "" };

export function criteriaActive(criteria: ListCriteria): boolean {
  return criteria.search.trim() !== "" || criteria.status !== "" || criteria.category !== "";
}

/** Accent-insensitive match, so « mobilier » finds « Mobilier ». */
export function matchesText(text: string, search: string): boolean {
  const needle = fold(search.trim());
  if (!needle) return true;
  return fold(text).includes(needle);
}

function fold(value: string): string {
  return value.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase("fr");
}

export interface ListSelectors<T> {
  text: (item: T) => string;
  status?: (item: T) => string;
  category?: (item: T) => string;
}

export function filterList<T>(
  items: readonly T[],
  criteria: ListCriteria,
  selectors: ListSelectors<T>,
): T[] {
  return items.filter((item) => {
    if (!matchesText(selectors.text(item), criteria.search)) return false;
    if (criteria.status && selectors.status && selectors.status(item) !== criteria.status) return false;
    if (criteria.category && selectors.category && selectors.category(item) !== criteria.category) return false;
    return true;
  });
}

export type ListOutcome = "empty" | "no-results" | "data";

/** `empty` is a successful response with nothing to show. Filters never count as empty. */
export function listOutcome(total: number, visible: number, filtered: boolean): ListOutcome {
  if (visible > 0) return "data";
  if (total === 0 && !filtered) return "empty";
  return "no-results";
}

export function groupByKey<T>(items: readonly T[], keyOf: (item: T) => string): { key: string; items: T[] }[] {
  const order: string[] = [];
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const key = keyOf(item);
    const bucket = groups.get(key);
    if (bucket) bucket.push(item);
    else {
      groups.set(key, [item]);
      order.push(key);
    }
  }
  return order.map((key) => ({ key, items: groups.get(key) ?? [] }));
}
