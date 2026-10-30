export const ROUTES = {
  home: "/",
  ledger: "/comptabilite",
  operations: "/operations",
  assets: "/immobilisations",
  statements: "/etats-comptables",
  fiscal: "/fiscalite",
  conservation: "/conservation",
} as const;

export type PageId = "overview" | "ledger" | "operations" | "assets" | "statements" | "fiscal" | "conservation";

export const LEDGER_TABS = [
  "Brouillons",
  "Journal",
  "Grand livre",
  "Balance",
  "Plan comptable",
  "Inventaire",
] as const;

export type LedgerTab = (typeof LEDGER_TABS)[number];

const ledgerSlugByTab: Record<LedgerTab, string> = {
  Brouillons: "brouillons",
  Journal: "journal",
  "Grand livre": "grand-livre",
  Balance: "balance",
  "Plan comptable": "plan-comptable",
  Inventaire: "inventaire",
};

const ledgerTabBySlug: Record<string, LedgerTab> = Object.fromEntries(
  Object.entries(ledgerSlugByTab).map(([tab, slug]) => [slug, tab as LedgerTab]),
);

export const DEFAULT_LEDGER_TAB: LedgerTab = "Brouillons";

export function ledgerPath(tab: LedgerTab = DEFAULT_LEDGER_TAB): string {
  return `${ROUTES.ledger}/${ledgerSlugByTab[tab]}`;
}

export function ledgerTabFromSlug(slug: string | undefined): LedgerTab | null {
  if (!slug) return null;
  return ledgerTabBySlug[slug] ?? null;
}

export const OPERATIONS_TABS = ["Biens", "Banque", "Emprunts", "Transactions"] as const;

export type OperationsTab = (typeof OPERATIONS_TABS)[number];

const operationsSlugByTab: Record<OperationsTab, string> = {
  Biens: "biens",
  Banque: "banque",
  Emprunts: "emprunts",
  Transactions: "transactions",
};

const operationsTabBySlug: Record<string, OperationsTab> = Object.fromEntries(
  Object.entries(operationsSlugByTab).map(([tab, slug]) => [slug, tab as OperationsTab]),
);

export const DEFAULT_OPERATIONS_TAB: OperationsTab = "Biens";

export function operationsPath(tab: OperationsTab = DEFAULT_OPERATIONS_TAB): string {
  return `${ROUTES.operations}/${operationsSlugByTab[tab]}`;
}

export function operationsTabFromSlug(slug: string | undefined): OperationsTab | null {
  if (!slug) return null;
  return operationsTabBySlug[slug] ?? null;
}

export const navItems: {
  id: PageId;
  label: string;
  step?: string;
  hint: string;
  path: string;
}[] = [
  { id: "overview", label: "Vue d’ensemble", hint: "Par où commencer.", path: ROUTES.home },
  { id: "ledger", label: "Comptabilité", step: "1", hint: "Activité, exercice, puis écritures validées.", path: ledgerPath() },
  { id: "operations", label: "Opérations & banque", step: "2", hint: "Bien, banque, emprunt, loyers et charges.", path: operationsPath() },
  { id: "assets", label: "Immobilisations", step: "3", hint: "Terrain, bâtiment, mobilier, puis dotations.", path: ROUTES.assets },
  { id: "statements", label: "États comptables", step: "4", hint: "Bilan, résultat, puis centralisation.", path: ROUTES.statements },
  { id: "fiscal", label: "Fiscalité LMNP", step: "5", hint: "Calcul fiscal, pré-contrôle, clôture, puis sorties figées.", path: ROUTES.fiscal },
  { id: "conservation", label: "Conservation", step: "6", hint: "Justificatifs et sauvegarde.", path: ROUTES.conservation },
];

export function viewDocumentTitle(label: string): string {
  return `${label} — SoloLMNP`;
}

export function pageIdFromPathname(pathname: string): PageId {
  if (pathname === ROUTES.home) return "overview";
  if (pathname.startsWith(ROUTES.ledger)) return "ledger";
  if (pathname.startsWith(ROUTES.operations)) return "operations";
  if (pathname.startsWith(ROUTES.assets)) return "assets";
  if (pathname.startsWith(ROUTES.statements)) return "statements";
  if (pathname.startsWith(ROUTES.fiscal)) return "fiscal";
  if (pathname.startsWith(ROUTES.conservation)) return "conservation";
  return "overview";
}
