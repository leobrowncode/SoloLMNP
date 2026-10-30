import { GLOSSARY } from "./glossary";
import type { ShowSaveNotice } from "./localFeedback";
import { operationsPath } from "../routing/paths";

const JOURNAL = "/comptabilite/journal";

function textName(data: Record<string, unknown>, key: string, fallback: string): string {
  const value = data[key];
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function numericId(result: Record<string, unknown>, pathId: string | undefined): number | null {
  if (typeof result.id === "number") return result.id;
  const parsed = Number(pathId);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

/** Where to put the acknowledgement for an opérations save, and what to say. */
export function operationSaveNotice(input: {
  path: string;
  method?: "POST" | "PATCH" | undefined;
  title: string;
  fixed?: Record<string, unknown> | undefined;
  data: Record<string, unknown>;
  result: Record<string, unknown>;
  detail?: string | undefined;
}): ShowSaveNotice {
  const { path, title, data, result } = input;
  const created = (input.method ?? "POST") === "POST";
  const detail = input.detail;

  if (path === "/properties" || /^\/properties\/\d+$/.test(path)) {
    const id = numericId(result, path.split("/")[2]);
    return {
      kind: "Bien",
      name: textName(data, "name", "logement"),
      action: created ? "créé" : "modifié",
      targetId: "biens-saisie",
      highlightId: id ? `bien-${id}` : undefined,
      detail,
      next: created
        ? { label: "Ajouter un compte bancaire", href: operationsPath("Banque") }
        : { label: "Préparer les loyers", href: `${operationsPath("Biens")}#biens-saisie` },
    };
  }

  const tenantProperty = path.match(/^\/properties\/(\d+)\/tenants/);
  if (tenantProperty) {
    return {
      kind: "Locataire",
      name: textName(data, "name", "locataire"),
      action: created ? "créé" : "modifié",
      targetId: "biens-saisie",
      highlightId: `bien-${tenantProperty[1]}`,
      detail,
      next: { label: "Préparer les loyers de l’exercice", href: `${operationsPath("Biens")}#biens-saisie` },
    };
  }

  if (path === "/banks" || /^\/banks\/\d+$/.test(path)) {
    const id = numericId(result, path.split("/")[2]);
    return {
      kind: "Compte bancaire",
      name: textName(data, "name", "banque"),
      action: created ? "créé" : "modifié",
      targetId: "banque-saisie",
      highlightId: id ? `banque-${id}` : undefined,
      detail,
      next: { label: "Importer un relevé", href: "/operations/banque#import-releve" },
    };
  }

  if (path === "/loans" || /^\/loans\/\d+$/.test(path)) {
    const id = numericId(result, path.split("/")[2]);
    return {
      kind: GLOSSARY.emprunt.label,
      name: textName(data, "lender", title.replace(/^Modifier /, "")),
      action: created ? "créé" : "modifié",
      targetId: "emprunts-saisie",
      highlightId: id ? `emprunt-${id}` : undefined,
      detail,
      next: { label: "Saisir une échéance", href: operationsPath("Emprunts") },
    };
  }

  if (path.endsWith("/fund")) {
    return {
      kind: "Déblocage",
      name: title.replace(/^Déblocage initial : /, ""),
      action: "enregistré",
      targetId: "emprunts-saisie",
      detail,
      next: { label: "Saisir une échéance", href: operationsPath("Emprunts") },
    };
  }

  if (path.endsWith("/payments")) {
    return {
      kind: "Échéance",
      name: title.replace(/^Échéance : /, ""),
      action: "comptabilisée",
      targetId: "emprunts-saisie",
      detail,
      next: { label: "Rapprocher le relevé", href: operationsPath("Banque") },
    };
  }

  if (path.endsWith("/settle")) {
    return {
      kind: "Règlement",
      name: title.replace(/^Régler : /, ""),
      action: "enregistré",
      targetId: "transactions-saisie",
      detail,
      next: { label: "Voir le journal", href: JOURNAL },
    };
  }

  if (path.endsWith("/reverse")) {
    return {
      kind: GLOSSARY.extourne.label,
      name: title.replace(/^Extourner : /, ""),
      action: "enregistrée",
      targetId: "transactions-saisie",
      detail,
      next: { label: "Voir le journal", href: JOURNAL },
    };
  }

  if (path.endsWith("/unmatch")) {
    const id = path.match(/\/bank\/transactions\/(\d+)/)?.[1];
    return {
      kind: GLOSSARY.rapprochement.label,
      name: title.replace(/^Annuler le rapprochement : /, "") || "mouvement",
      action: "annulé",
      targetId: "banque-saisie",
      highlightId: id ? `mouvement-${id}` : undefined,
      detail,
    };
  }

  if (path === "" || path === "/revenues" || path === "/expenses") {
    const expense = input.fixed?.kind === "EXPENSE" || path.includes("expense");
    const kind = expense ? "Dépense" : "Recette";
    const id = numericId(result, undefined);
    return {
      kind,
      name: textName(data, "description", kind),
      action: "enregistrée",
      targetId: "transactions-saisie",
      highlightId: id ? `operation-${id}` : undefined,
      detail,
      next: expense
        ? { label: "Vérifier la réintégration", href: "/fiscalite#calcul-fiscal" }
        : { label: "Voir le journal", href: JOURNAL },
    };
  }

  return {
    kind: "Opération",
    name: title,
    action: created ? "enregistrée" : "modifiée",
    targetId: "transactions-saisie",
    detail,
  };
}
