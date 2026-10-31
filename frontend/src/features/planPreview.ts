import { parseAmountToCents } from "../lib/format";

export interface PlanLine {
  kind: string;
  amount: string;
}

export interface PresentedPlan<T extends PlanLine> {
  lines: T[];
  building: T | null;
  /** True when component amounts already equal the building. It is a total, not an extra line. */
  buildingIsBreakdown: boolean;
}

function cents(amount: string): bigint | null {
  try {
    return parseAmountToCents(amount);
  } catch {
    return null;
  }
}

/**
 * The engine depreciates components, not the building on top of them.
 * When components sum exactly to the building, the preview shows the
 * building as a « dont » total and lists only land and components.
 */
export function presentPlan<T extends PlanLine>(items: readonly T[]): PresentedPlan<T> {
  const building = items.find((item) => item.kind === "BUILDING") ?? null;
  if (!building) return { lines: [...items], building: null, buildingIsBreakdown: false };
  const components = items.filter((item) => item.kind === "COMPONENT");
  const buildingCents = cents(building.amount);
  if (buildingCents === null || components.length === 0) {
    return { lines: [...items], building, buildingIsBreakdown: false };
  }
  let sum = 0n;
  for (const item of components) {
    const part = cents(item.amount);
    if (part === null) return { lines: [...items], building, buildingIsBreakdown: false };
    sum += part;
  }
  if (sum !== buildingCents) {
    return { lines: [...items], building, buildingIsBreakdown: false };
  }
  return {
    lines: items.filter((item) => item.kind !== "BUILDING"),
    building,
    buildingIsBreakdown: true,
  };
}
