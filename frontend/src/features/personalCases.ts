import { parseAmountToCents } from "../lib/format";

export interface PersonalCaseLine {
  case?: string | null;
  code?: string | null;
  amount?: string | null;
  served?: boolean;
}

function caseCode(line: PersonalCaseLine): string | null {
  const value = (line.case ?? line.code ?? "").trim();
  return value || null;
}

function nonzero(line: PersonalCaseLine): boolean {
  if (!line.amount) return false;
  try {
    return parseAmountToCents(line.amount) !== 0n;
  } catch {
    return true;
  }
}

export interface PersonalCaseView<T extends PersonalCaseLine> {
  shown: T[];
  /** Case that stays at zero and is not given its own row. */
  idleCase: string | null;
}

/**
 * 5NA and 5NY are alternatives. Show the case that carries the amount.
 * The other case is one sentence, not a second row at 0,00 €.
 */
export function visiblePersonalLines<T extends PersonalCaseLine>(
  lines: readonly T[],
): PersonalCaseView<T> {
  if (lines.length <= 1) return { shown: [...lines], idleCase: null };
  const served = lines.filter((line) => line.served === true);
  const idle = lines.filter((line) => line.served === false);
  if (served.length > 0) {
    return {
      shown: served,
      idleCase: idle.map(caseCode).find((code): code is string => Boolean(code)) ?? null,
    };
  }
  const carrying = lines.filter(nonzero);
  if (carrying.length === 1) {
    const hidden = lines.find((line) => !carrying.includes(line));
    return { shown: carrying, idleCase: hidden ? caseCode(hidden) : null };
  }
  if (carrying.length === 0) {
    const benefit = lines.find((line) => caseCode(line) === "5NA") ?? lines[0];
    if (!benefit) return { shown: [], idleCase: null };
    const other = lines.find((line) => line !== benefit);
    return { shown: [benefit], idleCase: other ? caseCode(other) : null };
  }
  return { shown: [...lines], idleCase: null };
}

export function idleCaseSentence(code: string): string {
  return `La case ${code} reste à 0.`;
}
