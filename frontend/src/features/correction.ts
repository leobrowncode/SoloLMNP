export interface CorrectionState {
  locks: { code: string; fields: string[]; message: string }[];
  calculated_periods: number;
}

export interface Invalidation {
  dropped_period_ids: number[];
  fiscal_computations: number;
  ready_years_reset: number[];
  snapshots_superseded: number;
}

export const PLAN_HELP =
  "La fiche n’est pas supprimée. L’historique conserve l’ancienne valeur, la nouvelle et le motif. Si le plan de cette fiche change, ses périodes calculées non comptabilisées sont effacées. Les calculs fiscaux des exercices ouverts sont invalidés. Un exercice prêt à clôturer redevient ouvert. Les écritures validées restent.";

export const RECORD_HELP =
  "La fiche n’est pas supprimée. L’historique conserve l’ancienne valeur, la nouvelle et le motif. Les écritures validées ne sont pas réécrites.";

export function locked(state: CorrectionState | undefined, group: string): boolean {
  return state?.locks.some((lock) => lock.fields.includes(group)) ?? false;
}

export function editTitle(label: string, state: CorrectionState | undefined, groups: string[]): string {
  if (groups.length > 0 && groups.every((group) => locked(state, group))) {
    return `Préciser la justification de ${label}`;
  }
  return `Modifier ${label}`;
}

export function correctionMessage(invalidation: Invalidation): string {
  const parts = [
    "Correction enregistrée. L’historique conserve l’ancienne valeur, la nouvelle et le motif.",
  ];
  if (invalidation.dropped_period_ids.length) {
    parts.push(
      `${invalidation.dropped_period_ids.length} période(s) calculée(s) non comptabilisée(s) ont été effacées. Relancez le calcul.`,
    );
  }
  if (invalidation.fiscal_computations) {
    parts.push(`${invalidation.fiscal_computations} calcul(s) fiscal(aux) d’exercice ouvert invalidé(s).`);
  }
  if (invalidation.ready_years_reset.length) {
    parts.push(
      `${invalidation.ready_years_reset.length} exercice(s) prêt(s) à clôturer repassé(s) à ouvert.`,
    );
  }
  if (invalidation.snapshots_superseded) {
    parts.push(
      `${invalidation.snapshots_superseded} instantané(s) de liasse ouvert(s) marqué(s) comme remplacé(s).`,
    );
  }
  parts.push("Les écritures validées, et donc le FEC, ne sont pas réécrits.");
  return parts.join(" ");
}

export function readInvalidation(value: unknown): Invalidation | null {
  if (typeof value !== "object" || value === null || !("dropped_period_ids" in value)) return null;
  return value as Invalidation;
}
