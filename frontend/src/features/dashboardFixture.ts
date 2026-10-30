import type { DashboardContinue, DashboardPayload, DashboardProgression, DashboardStep, DashboardStepId, DashboardStepStatus } from "../api/dashboard";
import { DASHBOARD_STATUS_LABELS } from "../api/dashboard";
import type { DossierStatus } from "../api/status";

const LABELS: Record<DashboardStepId, string> = {
  structure: "Structure et SIREN",
  operations: "Opérations",
  assets: "Immobilisations et amortissements",
  opening: "À-nouveaux",
  closing: "Clôture",
  filing: "Fiscalité et exports",
};

function dossier(
  status: DossierStatus["status"],
  label: DossierStatus["label"],
  yearStatus: DossierStatus["year_status"],
  year: number | null,
): DossierStatus {
  return {
    status,
    label,
    fiscal_year_id: year === null ? null : 1,
    year,
    year_status: yearStatus,
    vintage_status: "research_only",
  };
}

function step(
  id: DashboardStepId,
  status: DashboardStepStatus,
  summary: string,
  extra: Partial<DashboardStep> = {},
): DashboardStep {
  return {
    id,
    label: LABELS[id],
    status,
    status_label: DASHBOARD_STATUS_LABELS[status],
    summary,
    prerequisites: [],
    last_event: null,
    amount_cents: null,
    ...extra,
  };
}

const siren = {
  code: "SIREN_REQUIRED",
  message: "Le SIREN n’est pas renseigné.",
  action: { label: "Renseigner le SIREN", href: "/comptabilite/brouillons#identite-liasse" },
};

function attach(
  payload: Omit<DashboardPayload, "progression">,
): DashboardPayload {
  const steps = payload.steps;
  const next: DashboardContinue = payload.continue;
  let progression: DashboardProgression;
  if (steps.length === 0) {
    progression = {
      done: 0,
      total: 0,
      label: "0/0",
      current_step: next.step,
      current_label: LABELS[next.step],
      current_status: "a_faire",
      current_status_label: "À faire",
      summary: "Aucun dossier à afficher.",
    };
  } else {
    const done = steps.filter((item) => item.status === "fait").length;
    const current = steps.find((item) => item.id === next.step) ?? steps[0];
    if (!current) throw new Error("Étape de progression absente.");
    progression = {
      done,
      total: steps.length,
      label: `${done}/${steps.length}`,
      current_step: current.id,
      current_label: current.label,
      current_status: current.status,
      current_status_label: current.status_label,
      summary: current.summary,
    };
  }
  return { ...payload, progression };
}

export function dashboardFixture(
  kind: "empty" | "partial" | "blocked" | "ready" | "blank" | "followingBlocked" | "followingOpen" | "followingPosted",
): DashboardPayload {
  if (kind === "blank") {
    return attach({
      dossier: dossier("incomplet", "Incomplet", null, null),
      continue: {
        label: "Continuer",
        href: "/comptabilite/brouillons#creer-activite",
        detail: "Prochaine action : Créer l’activité.",
        step: "structure",
      },
      steps: [],
    });
  }
  if (kind === "empty") {
    return attach({
      dossier: dossier("incomplet", "Incomplet", null, null),
      continue: {
        label: "Continuer",
        href: "/comptabilite/brouillons#creer-activite",
        detail: "Prochaine action : Créer l’activité.",
        step: "structure",
      },
      steps: (Object.keys(LABELS) as DashboardStepId[]).map((id) => step(
        id,
        "a_faire",
        id === "structure" ? "L’activité n’est pas créée." : "L’activité n’est pas créée.",
        id === "structure"
          ? { prerequisites: [{ code: "NO_ACTIVITY", message: "L’activité n’est pas créée.", action: { label: "Créer l’activité", href: "/comptabilite/brouillons#creer-activite" } }] }
          : {},
      )),
    });
  }
  if (kind === "partial") {
    return attach({
      dossier: dossier("incomplet", "Incomplet", "OPEN", 2026),
      continue: {
        label: "Continuer",
        href: "/comptabilite/brouillons#identite-liasse",
        detail: "Prochaine action : Renseigner le SIREN.",
        step: "structure",
      },
      steps: [
        step("structure", "en_cours", "Le SIREN n’est pas renseigné.", {
          prerequisites: [siren],
          last_event: { occurred_at: "2026-03-02T09:30:00Z", label: "Exercice 2026 créé" },
        }),
        step("operations", "a_faire", "Aucun bien n’est enregistré.", {
          prerequisites: [{
            code: "NO_PROPERTY",
            message: "Aucun bien n’est enregistré.",
            action: { label: "Ajouter un bien", href: "/operations/biens#ajouter-bien" },
          }],
        }),
        step("assets", "a_faire", "Aucun bien n’est enregistré."),
        step("opening", "fait", "Premier exercice : aucun à-nouveaux à reprendre."),
        step("closing", "en_cours", "Aucun calcul fiscal n’est enregistré pour cet exercice.", {
          prerequisites: [{
            code: "FISCAL_NOT_COMPUTED",
            message: "Aucun calcul fiscal n’est enregistré pour cet exercice.",
            action: { label: "Calculer le résultat fiscal", href: "/fiscalite#calcul-fiscal" },
          }],
        }),
        step("filing", "en_cours", "Calculez le résultat fiscal avant de télécharger la liasse ou le PDF."),
      ],
    });
  }
  if (kind === "blocked") {
    return attach({
      dossier: dossier("bloque", "Bloqué", "OPEN", 2026),
      continue: {
        label: "Continuer",
        href: "/comptabilite/brouillons#identite-liasse",
        detail: "Prochaine action : Renseigner le SIREN.",
        step: "structure",
      },
      steps: [
        step("structure", "bloque", "Le SIREN n’est pas renseigné.", { prerequisites: [siren] }),
        step("operations", "fait", "Des opérations sont enregistrées.", { amount_cents: 12345 }),
        step("assets", "fait", "Les dotations de l’exercice sont comptabilisées.", { amount_cents: 2500 }),
        step("opening", "fait", "Premier exercice : aucun à-nouveaux à reprendre."),
        step("closing", "en_cours", "Le pré-contrôle reste à terminer."),
        step("filing", "bloque", "Liasse Bloquée. PDF Bloquée. FEC Bloquée. Millésime en recherche.", {
          amount_cents: 0,
          prerequisites: [{
            code: "SIREN_MANQUANT",
            message: "Indiquez le SIREN de l’activité (Comptabilité → Identité).",
            action: { label: "Renseigner le SIREN", href: "/comptabilite/brouillons#identite-liasse" },
          }],
        }),
      ],
    });
  }
  if (kind === "followingBlocked" || kind === "followingOpen" || kind === "followingPosted") {
    const opening = kind === "followingPosted"
      ? step("opening", "fait", "Les à-nouveaux sont comptabilisés.", { amount_cents: 250050 })
      : kind === "followingBlocked"
        ? step("opening", "bloque", "L’exercice précédent n’est pas clôturé : ces soldes peuvent changer.", {
          prerequisites: [{
            code: "SOURCE_NOT_CLOSED",
            message: "L’exercice précédent n’est pas clôturé : ces soldes peuvent changer.",
            action: { label: "Clôturer l’exercice précédent", href: "/fiscalite#close-title" },
          }],
        })
        : step("opening", "en_cours", "Les à-nouveaux ne sont pas comptabilisés.", {
          prerequisites: [{
            code: "OPENING_MISSING",
            message: "Les à-nouveaux ne sont pas comptabilisés.",
            action: { label: "Prévisualiser les à-nouveaux", href: "/etats-comptables#opening-title" },
          }],
        });
    const closingReady = kind === "followingOpen";
    const next: DashboardContinue = kind === "followingBlocked"
      ? {
        label: "Continuer",
        href: "/fiscalite#close-title",
        detail: "Prochaine action : Clôturer l’exercice précédent.",
        step: "opening",
      }
      : kind === "followingOpen"
        ? {
          label: "Continuer",
          href: "/etats-comptables#opening-title",
          detail: "Prochaine action : Prévisualiser les à-nouveaux.",
          step: "opening",
        }
        : {
          label: "Continuer",
          href: "/fiscalite#calcul-fiscal",
          detail: "Prochaine action : Calculer le résultat fiscal.",
          step: "closing",
        };
    return attach({
      dossier: dossier("incomplet", "Incomplet", "OPEN", 2026),
      continue: next,
      steps: [
        step("structure", "fait", "Activité, exercice 2026 et SIREN sont en place."),
        step("operations", "fait", "Des opérations sont enregistrées.", { amount_cents: 5000 }),
        step("assets", "fait", "Les dotations de l’exercice sont comptabilisées.", { amount_cents: 1000 }),
        opening,
        closingReady
          ? step("closing", "pret", "Le pré-contrôle ne bloque pas. Préparez la clôture.")
          : step("closing", "en_cours", "Aucun calcul fiscal n’est enregistré pour cet exercice.", {
            prerequisites: [{
              code: "FISCAL_NOT_COMPUTED",
              message: "Aucun calcul fiscal n’est enregistré pour cet exercice.",
              action: { label: "Calculer le résultat fiscal", href: "/fiscalite#calcul-fiscal" },
            }],
          }),
        step("filing", "en_cours", "Aucun calcul fiscal n’est enregistré pour cet exercice. Millésime en recherche."),
      ],
    });
  }
  return attach({
    dossier: dossier("pret_a_verifier", "Prêt à vérifier", "READY_TO_CLOSE", 2026),
    continue: {
      label: "Continuer",
      href: "/fiscalite#close-title",
      detail: "Prochaine action : confirmer la clôture.",
      step: "closing",
    },
    steps: [
      step("structure", "fait", "Activité, exercice 2026 et SIREN sont en place."),
      step("operations", "fait", "Des opérations sont enregistrées. La saisie est figée.", { amount_cents: 10000 }),
      step("assets", "fait", "Les dotations de l’exercice sont comptabilisées.", { amount_cents: 2500 }),
      step("opening", "fait", "Premier exercice : aucun à-nouveaux à reprendre."),
      step("closing", "pret", "Exercice prêt à clôturer.", {
        last_event: { occurred_at: "2026-12-31T18:00:00Z", label: "Exercice passé en prêt à clôturer" },
      }),
      step("filing", "pret", "Liasse Provisoire. PDF Provisoire. FEC Bloquée. Millésime en recherche.", {
        amount_cents: 0,
        prerequisites: [{
          code: "YEAR_NOT_CLOSED",
          message: "Le FEC final et le dossier de contrôle exigent un exercice clôturé.",
          action: { label: "Clôturer l’exercice", href: "/fiscalite#close-title" },
        }],
      }),
    ],
  });
}
