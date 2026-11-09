/** Identity and exercise defaults for the declaration setup, before any request. */

export interface IdentityDraft {
  siren: string;
  siret: string;
}

export function onlyDigits(value: string, max: number): string {
  return value.replace(/\D/g, "").slice(0, max);
}

/** A SIRET of at least 9 digits owns the SIREN. Clearing a derived SIRET clears it too. */
export function identityFromSiret(raw: string, previous: IdentityDraft): IdentityDraft {
  const siret = onlyDigits(raw, 14);
  if (siret.length >= 9) return { siret, siren: siret.slice(0, 9) };
  const derived = previous.siret.length >= 9 && previous.siren === previous.siret.slice(0, 9);
  return { siret, siren: derived ? "" : previous.siren };
}

/** Nine digits stay a SIREN. A 14-digit paste is a SIRET and fills both. */
export function identityFromSiren(raw: string, previous: IdentityDraft): IdentityDraft {
  const cleaned = onlyDigits(raw, 14);
  if (cleaned.length > 9) return { siret: cleaned, siren: cleaned.slice(0, 9) };
  if (previous.siret && !previous.siret.startsWith(cleaned)) return { siren: cleaned, siret: "" };
  return { siren: cleaned, siret: previous.siret };
}

export function sirenDerivedFromSiret(draft: IdentityDraft): boolean {
  return draft.siret.length >= 9 && draft.siren === draft.siret.slice(0, 9);
}

export function identityIssue(draft: IdentityDraft): string {
  if (draft.siret && draft.siret.length !== 14) {
    return "Le SIRET comporte 14 chiffres. Les 9 premiers sont le SIREN.";
  }
  if (draft.siren && draft.siren.length !== 9) return "Le SIREN comporte 9 chiffres.";
  if (!draft.siren) return "Indiquez le SIRET, ou le SIREN si vous n’avez pas le SIRET.";
  if (draft.siret && !draft.siret.startsWith(draft.siren)) {
    return "Le SIRET doit commencer par le SIREN.";
  }
  return "";
}

/** First exercise: from the activity start through 31 December of that year. */
export function suggestedExercise(activityStart: string | null | undefined): {
  start: string;
  end: string;
  vintage: string;
} | null {
  if (!activityStart || !/^\d{4}-\d{2}-\d{2}$/.test(activityStart)) return null;
  const year = activityStart.slice(0, 4);
  const end = `${year}-12-31`;
  if (activityStart > end) return null;
  return { start: activityStart, end, vintage: year };
}

export interface GuideLocationState {
  guideNote?: string;
}

export function guideNoteFrom(state: unknown): string {
  if (!state || typeof state !== "object" || !("guideNote" in state)) return "";
  const note = (state as GuideLocationState).guideNote;
  return typeof note === "string" ? note : "";
}

/** Drop or rewrite setup banners once the dossier has moved past the rail step they describe. */
export function guideNoteForOperations(
  state: unknown,
  propertyCount: number,
  bankCount: number,
): string {
  const note = guideNoteFrom(state);
  if (!note) return "";
  if (propertyCount > 0) {
    if (bankCount === 0) return "Logement enregistré. Ajoutez un compte bancaire.";
    return "";
  }
  return note;
}

export const DECLARATION_STEPS = [
  { id: "siret", label: "SIRET" },
  { id: "exercice", label: "Exercice" },
  { id: "bien", label: "Bien" },
  { id: "banque", label: "Banque" },
] as const;

export type DeclarationStepId = (typeof DECLARATION_STEPS)[number]["id"];
