export interface CauseAction {
  label: string;
  href: string;
}

export interface ActionCause {
  code: string;
  message: string;
  action: CauseAction;
}

export const FIX = {
  activity: { label: "Créer l’activité", href: "/comptabilite/brouillons#creer-activite" },
  year: { label: "Créer un exercice", href: "/comptabilite/brouillons#ajouter-exercice" },
  exercise: { label: "Voir l’exercice", href: "/comptabilite/brouillons#exercice" },
  reopen: { label: "Réouvrir l’exercice", href: "/fiscalite#reopen-title" },
  close: { label: "Voir le pré-contrôle", href: "/fiscalite#close-title" },
  closePrepare: { label: "Accuser et préparer la clôture", href: "/fiscalite#close-prepare" },
  property: { label: "Ajouter un bien", href: "/operations/biens#ajouter-bien" },
  bank: { label: "Ajouter un compte bancaire", href: "/operations/banque#ajouter-banque" },
  drafts: { label: "Valider les brouillons", href: "/comptabilite/brouillons#nouvelle-ecriture" },
  journal: { label: "Consulter le journal", href: "/comptabilite/journal" },
  chart: { label: "Ouvrir le plan comptable", href: "/comptabilite/plan-comptable" },
  identity: { label: "Renseigner le SIREN", href: "/comptabilite/brouillons#identite-liasse" },
  fiscal: { label: "Calculer le résultat fiscal", href: "/fiscalite#calcul-fiscal" },
  centralize: { label: "Centraliser le résultat", href: "/etats-comptables#result-title" },
  depreciation: { label: "Comptabiliser les dotations", href: "/immobilisations#dotations" },
  enterProperty: { label: "Faire entrer le bien en comptabilité", href: "/immobilisations#entree-bien" },
  bookAsset: { label: "Inscrire l’immobilisation au journal", href: "/comptabilite/brouillons#nouvelle-ecriture" },
  opening: { label: "Prévisualiser les à-nouveaux", href: "/etats-comptables#opening-title" },
  statements: { label: "Vérifier les états", href: "/etats-comptables#statements-title" },
  calculatePeriods: { label: "Calculer les périodes", href: "/immobilisations#calculer-periodes" },
  dotations: { label: "Voir les dotations", href: "/immobilisations#dotations" },
  entryPreview: { label: "Prévisualiser l’écriture", href: "/immobilisations#property-entry-preview" },
  inventory: { label: "Revenir à l’inventaire", href: "/comptabilite/inventaire" },
  reopenReason: { label: "Saisir le motif", href: "/fiscalite#reopen-motif" },
  reopenConfirm: { label: "Saisir ROUVRIR", href: "/fiscalite#reopen-confirmation" },
} as const satisfies Record<string, CauseAction>;

const PRECHECK: Record<string, CauseAction> = {
  YEAR_DRAFTS: FIX.drafts,
  CENTRALIZATION_REQUIRED: FIX.centralize,
  CENTRALIZATION_STALE: FIX.centralize,
  DEPRECIATION_UNPOSTED: FIX.depreciation,
  FISCAL_NOT_COMPUTED: FIX.fiscal,
  FISCAL_STALE: FIX.fiscal,
  SIREN_REQUIRED: FIX.identity,
  ASSET_NOT_BOOKED: FIX.enterProperty,
  ASSET_PURCHASE_UNBOOKED: FIX.bookAsset,
  IMMOBILISATIONS_ECART: FIX.enterProperty,
  IMMOBILISATIONS_NETTES_NEGATIVES: FIX.enterProperty,
};

const OPENING_BLOCKERS: Record<string, CauseAction> = {
  SOURCE_NOT_CLOSED: { label: "Clôturer l’exercice précédent", href: FIX.close.href },
  SOURCE_DRAFTS: FIX.drafts,
  TARGET_NOT_OPEN: { label: "Voir la clôture de l’exercice", href: FIX.close.href },
  TARGET_HAS_ENTRIES: FIX.journal,
  INACTIVE_ACCOUNTS: { label: "Réactiver les comptes", href: FIX.chart.href },
};

export function describedBy(id: string, causes: readonly unknown[], extra?: string): string | undefined {
  const ids = [causes.length > 0 ? id : "", extra ?? ""].filter((value) => value !== "");
  return ids.length > 0 ? ids.join(" ") : undefined;
}

export function listed(...items: (ActionCause | null | false | undefined)[]): ActionCause[] {
  return items.filter((item): item is ActionCause => Boolean(item));
}

export function activityCause(present: boolean): ActionCause | null {
  if (present) return null;
  return {
    code: "NO_ACTIVITY",
    message: "L’activité n’est pas créée.",
    action: FIX.activity,
  };
}

export function propertyCause(count: number): ActionCause | null {
  if (count > 0) return null;
  return {
    code: "NO_PROPERTY",
    message: "Aucun bien n’est enregistré.",
    action: FIX.property,
  };
}

export function bankCause(count: number): ActionCause | null {
  if (count > 0) return null;
  return {
    code: "NO_BANK",
    message: "Aucun compte bancaire n’est enregistré.",
    action: FIX.bank,
  };
}

export function tenantCause(propertyId: number, count: number): ActionCause | null {
  if (count > 0) return null;
  return {
    code: "NO_TENANT",
    message: "Ce bien n’a pas de colocataire.",
    action: {
      label: "Ajouter un colocataire",
      href: `/operations/biens#colocataires-${propertyId}`,
    },
  };
}

function isOpenYear(year: { status?: string }): boolean {
  return year.status === undefined || year.status === "OPEN";
}

export function openYearCauses(years: readonly { status?: string }[]): ActionCause[] {
  if (years.some((year) => isOpenYear(year))) return [];
  if (years.length === 0) {
    return [{
      code: "NO_YEAR",
      message: "Aucun exercice n’est créé.",
      action: FIX.year,
    }];
  }
  const causes: ActionCause[] = [];
  if (years.some((year) => year.status === "CLOSED")) {
    causes.push({
      code: "YEAR_CLOSED",
      message: "Aucun exercice n’est ouvert : au moins un exercice est clôturé.",
      action: FIX.reopen,
    });
  }
  if (years.some((year) => year.status === "READY_TO_CLOSE")) {
    causes.push({
      code: "YEAR_READY_TO_CLOSE",
      message: "Aucun exercice n’est ouvert : au moins un exercice est prêt à clôturer.",
      action: FIX.close,
    });
  }
  if (causes.length === 0) {
    causes.push({
      code: "NO_OPEN_YEAR",
      message: "Aucun exercice n’est ouvert à la saisie.",
      action: FIX.year,
    });
  }
  return causes;
}

export function selectedYearCauses(status: string | undefined): ActionCause[] {
  if (status === undefined || status === "OPEN") return [];
  if (status === "CLOSED") {
    return [{
      code: "YEAR_CLOSED",
      message: "Cet exercice est clôturé : la saisie est figée.",
      action: FIX.reopen,
    }];
  }
  if (status === "READY_TO_CLOSE") {
    return [{
      code: "YEAR_READY_TO_CLOSE",
      message: "Cet exercice est prêt à clôturer : la saisie est figée.",
      action: FIX.close,
    }];
  }
  return [{
    code: "YEAR_NOT_OPEN",
    message: "Cet exercice n’est pas ouvert à la saisie.",
    action: FIX.exercise,
  }];
}

export function operationEntryCauses(
  propertyCount: number,
  years: readonly { status?: string }[],
): ActionCause[] {
  return [...listed(propertyCause(propertyCount)), ...openYearCauses(years)];
}

export function rentCauses(
  propertyId: number,
  tenantCount: number,
  years: readonly { status?: string }[],
): ActionCause[] {
  return [...openYearCauses(years), ...listed(tenantCause(propertyId, tenantCount))];
}

export function assetCreateCauses(propertyCount: number): ActionCause[] {
  return listed(propertyCause(propertyCount));
}

export function depreciationCalculateCauses(
  yearId: number,
  years: readonly { status?: string }[],
): ActionCause[] {
  if (yearId) return [];
  return openYearCauses(years);
}

const ENTRY_BEFORE_DOTATION = "Le bien n’est pas entré en comptabilité : le brut du registre n’est pas au journal. Faites entrer le bien avant de comptabiliser les dotations.";
const JOURNAL_BEFORE_DOTATION = "L’immobilisation acquise pendant l’exercice n’est pas au journal. Inscrivez son brut au compte d’immobilisation avant de comptabiliser la dotation.";

export function postDepreciationCauses(
  periods: readonly { status: string; asset_on_ledger?: boolean; booking?: string }[],
): ActionCause[] {
  const pending = periods.filter((row) => row.status !== "POSTED");
  const unbooked = pending.filter((row) => row.asset_on_ledger === false);
  if (unbooked.length > 0) {
    if (unbooked.every((row) => row.booking === "journal")) {
      return [{
        code: "ASSET_PURCHASE_UNBOOKED",
        message: JOURNAL_BEFORE_DOTATION,
        action: FIX.bookAsset,
      }];
    }
    return [{
      code: "ASSET_NOT_BOOKED",
      message: ENTRY_BEFORE_DOTATION,
      action: FIX.enterProperty,
    }];
  }
  if (periods.some((row) => row.status !== "POSTED")) return [];
  if (periods.length === 0) {
    return [{
      code: "NO_PERIOD",
      message: "Aucune période d’amortissement n’est calculée.",
      action: FIX.calculatePeriods,
    }];
  }
  return [{
    code: "ALL_POSTED",
    message: "Toutes les dotations affichées sont déjà comptabilisées.",
    action: FIX.dotations,
  }];
}

export function propertyEntryStartCauses(
  propertyCount: number,
  years: readonly { status?: string }[],
): ActionCause[] {
  return operationEntryCauses(propertyCount, years);
}

export function propertyEntryPreviewCauses(propertyId: number, yearId: number): ActionCause[] {
  return listed(
    propertyId ? null : propertyCause(0),
    yearId ? null : {
      code: "NO_OPEN_YEAR",
      message: "Aucun exercice ouvert n’est choisi.",
      action: FIX.year,
    },
  );
}

export function propertyEntryPostCauses(hasPreview: boolean): ActionCause[] {
  if (hasPreview) return [];
  return [{
    code: "NO_ENTRY_PREVIEW",
    message: "Prévisualisez l’écriture avant de la comptabiliser.",
    action: FIX.entryPreview,
  }];
}

export interface OpeningLike {
  preview_token?: string;
  total_debit: string;
  warnings: { code: string; message: string }[];
}

export function openingGenerationCauses(preview: OpeningLike | null): ActionCause[] {
  if (!preview) return [];
  const causes: ActionCause[] = [];
  if (!preview.preview_token) {
    causes.push({
      code: "NO_PREVIEW_TOKEN",
      message: "La prévisualisation ne peut pas être comptabilisée.",
      action: FIX.opening,
    });
  }
  if (preview.total_debit === "0.00") {
    causes.push({
      code: "EMPTY_OPENING",
      message: "Aucun solde à reprendre.",
      action: FIX.statements,
    });
  }
  for (const warning of preview.warnings) {
    const action = OPENING_BLOCKERS[warning.code];
    if (!action) continue;
    causes.push({ code: warning.code, message: warning.message, action });
  }
  return causes;
}

export function unbalancedCause(entryId: number): ActionCause {
  return {
    code: "UNBALANCED",
    message: "L’écriture n’est pas équilibrée.",
    action: { label: "Corriger le brouillon", href: `/comptabilite/brouillons#ecriture-${entryId}` },
  };
}

export function reversalCause(): ActionCause {
  return {
    code: "ALREADY_REVERSAL",
    message: "Cette écriture est déjà une extourne.",
    action: FIX.journal,
  };
}

export function inventoryVerifyCauses(input: {
  yearStatus: string;
  generalJournalCount: number;
  recoveryError: string;
  attempted: boolean;
}): ActionCause[] {
  if (input.attempted) return [];
  return [
    ...selectedYearCauses(input.yearStatus),
    ...listed(
      input.generalJournalCount === 0 ? {
        code: "NO_GENERAL_JOURNAL",
        message: "Aucun journal actif d’opérations diverses disponible.",
        action: FIX.drafts,
      } : null,
      input.recoveryError ? {
        code: "INVENTORY_RECOVERY",
        message: input.recoveryError,
        action: FIX.inventory,
      } : null,
    ),
  ];
}

export function centralizationCauses(
  yearStatus: string,
  missingAccount: boolean,
  prefix: string | null,
): ActionCause[] {
  return [
    ...selectedYearCauses(yearStatus),
    ...listed(missingAccount ? {
      code: "RESULT_ACCOUNT",
      message: `Aucun compte actif ${prefix ?? ""} (hors 1209). Réactivez-le ou créez-en un dans le plan de comptes.`,
      action: FIX.chart,
    } : null),
  ];
}

export function precheckAction(code: string): CauseAction {
  return PRECHECK[code] ?? FIX.close;
}

export function closePrepareCauses(input: {
  sealed: boolean;
  blocking: boolean;
  errors: readonly { code: string; message: string }[];
  warnings: readonly { code: string }[];
  acks: readonly string[];
}): ActionCause[] {
  return [
    ...listed(input.sealed ? {
      code: "SEALED",
      message: "L’exercice est déjà clôturé.",
      action: FIX.reopen,
    } : null),
    ...blockingCauses(input.blocking, input.errors),
    ...listed(!acknowledgedExactly(input.warnings, input.acks) ? {
      code: "WARNINGS_UNACKED",
      message: "Chaque avertissement affiché doit être coché.",
      action: FIX.close,
    } : null),
  ];
}

export function closeConfirmCauses(input: {
  prepared: boolean;
  sealed: boolean;
  blocking: boolean;
  errors: readonly { code: string; message: string }[];
}): ActionCause[] {
  return [
    ...listed(!input.prepared ? {
      code: "NOT_PREPARED",
      message: "La clôture n’est pas encore préparée.",
      action: FIX.closePrepare,
    } : null),
    ...listed(input.sealed ? {
      code: "SEALED",
      message: "L’exercice est déjà clôturé.",
      action: FIX.reopen,
    } : null),
    ...blockingCauses(input.blocking, input.errors),
  ];
}

function blockingCauses(
  blocking: boolean,
  errors: readonly { code: string; message: string }[],
): ActionCause[] {
  if (!blocking) return [];
  if (errors.length === 0) {
    return [{
      code: "BLOCKING",
      message: "Le pré-contrôle signale une erreur.",
      action: FIX.close,
    }];
  }
  return errors.map((error) => ({
    code: error.code,
    message: error.message,
    action: precheckAction(error.code),
  }));
}

function acknowledgedExactly(warnings: readonly { code: string }[], acks: readonly string[]): boolean {
  const expected = new Set(warnings.map((item) => item.code));
  return acks.length === expected.size && acks.every((code) => expected.has(code));
}

export function reopenCauses(confirmation: string, reason: string): ActionCause[] {
  return listed(
    reason.trim().length < 10 ? {
      code: "REOPEN_REASON",
      message: "Le motif doit comporter au moins 10 caractères.",
      action: FIX.reopenReason,
    } : null,
    confirmation !== "ROUVRIR" ? {
      code: "REOPEN_CONFIRMATION",
      message: "La confirmation doit être exactement ROUVRIR.",
      action: FIX.reopenConfirm,
    } : null,
  );
}

export function linkCauses(selected: boolean): ActionCause[] {
  return listed(
    !selected ? {
      code: "ENTRY_PICK",
      message: "Choisissez une écriture par son numéro, sa date ou sa pièce.",
      action: { label: "Choisir une écriture", href: "/conservation#entry-picker" },
    } : null,
  );
}

export function restoreCauses(selected: boolean, previewReady: boolean, confirmation: string): ActionCause[] {
  return listed(
    !selected ? {
      code: "RESTORE_BACKUP",
      message: "Choisissez une sauvegarde connue de la liste.",
      action: { label: "Voir les sauvegardes", href: "/conservation#sauvegardes" },
    } : null,
    selected && !previewReady ? {
      code: "RESTORE_PREVIEW",
      message: "L’aperçu de la restauration n’est pas affiché.",
      action: { label: "Voir l’aperçu", href: "/conservation#restore-preview" },
    } : null,
    confirmation !== "RESTAURER" ? {
      code: "RESTORE_CONFIRMATION",
      message: "La confirmation doit être exactement RESTAURER.",
      action: { label: "Saisir RESTAURER", href: "/conservation#restore-confirmation" },
    } : null,
  );
}

export function fiscalActionCauses(yearId: number, years: readonly { status?: string }[]): ActionCause[] {
  if (yearId) return [];
  return openYearCauses(years);
}

export function csvPreviewCauses(input: {
  hasContent: boolean;
  anchor: string;
  missingProperty: boolean;
  missingYear: boolean;
  missingBank: boolean;
  missingLoan: boolean;
}): ActionCause[] {
  return listed(
    input.hasContent ? null : {
      code: "NO_CSV",
      message: "Collez ou chargez un fichier avant de prévisualiser.",
      action: { label: "Revenir au fichier", href: input.anchor },
    },
    input.missingProperty ? propertyCause(0) : null,
    input.missingYear ? {
      code: "NO_OPEN_YEAR",
      message: "Aucun exercice ouvert n’est choisi.",
      action: FIX.year,
    } : null,
    input.missingBank ? bankCause(0) : null,
    input.missingLoan ? {
      code: "NO_LOAN",
      message: "Aucun emprunt n’est choisi.",
      action: { label: "Ajouter un emprunt", href: "/operations/emprunts#ajouter-emprunt" },
    } : null,
  );
}

export function duplicatePostCauses(allDuplicates: boolean, href: string): ActionCause[] {
  if (!allDuplicates) return [];
  return [{
    code: "ALL_DUPLICATES",
    message: "Toutes les lignes affichées sont déjà comptabilisées.",
    action: { label: "Revoir l’aperçu", href },
  }];
}

export function loanPostCauses(confirmed: boolean, hasNewRows: boolean): ActionCause[] {
  return listed(
    !hasNewRows ? {
      code: "ALL_DUPLICATES",
      message: "Toutes les échéances affichées sont déjà comptabilisées.",
      action: { label: "Revoir l’aperçu", href: "/operations/emprunts#import-echeances" },
    } : null,
    hasNewRows && !confirmed ? {
      code: "MAPPING_UNCONFIRMED",
      message: "Confirmez que le prêt source correspond à l’emprunt choisi.",
      action: { label: "Confirmer la correspondance", href: "/operations/emprunts#confirmer-pret" },
    } : null,
  );
}
