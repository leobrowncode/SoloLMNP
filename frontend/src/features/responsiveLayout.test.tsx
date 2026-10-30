import { readFileSync } from "node:fs";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { dashboardFixture } from "./dashboardFixture";
import AssetsPage from "./AssetsPage";
import ChartOfAccounts from "./ChartOfAccounts";
import CsvImportAssistant from "./CsvImportAssistant";
import LedgerPage from "./LedgerPage";
import { navItems, ledgerPath } from "../routing/paths";
import { renderAt } from "../routing/renderTestApp";
import { renderWithRouter } from "../routing/testPage";

const WIDTHS = [320, 390, 768] as const;

const ready = {
  application_version: "0.2.0",
  phase: "foundation",
  database: { status: "ready", schema_revision: "0001_foundation", expected_revision: "0001_foundation" },
  fiscal: { status: "research_only", available_vintages: [] },
  dossier: {
    status: "pret_a_verifier",
    label: "Prêt à vérifier",
    fiscal_year_id: 1,
    year: 2026,
    year_status: "OPEN",
    vintage_status: "research_only",
  },
};

const accounts = [
  { number: "512000", label: "Banque", active: true, account_type: "ASSET" },
  { number: "706000", label: "Loyers", active: true, account_type: "INCOME" },
];

const journalEntry = {
  id: 7,
  version: 1,
  fiscal_year_id: 1,
  journal_code: "OD",
  accounting_date: "2025-03-01",
  piece_date: "2025-03-01",
  piece_reference: "P-1",
  label: "Loyer mars",
  status: "VALIDATED",
  entry_number: "OD-1",
  total_debit: "10.00",
  total_credit: "10.00",
  balanced: true,
  reversal_of_id: null,
  lines: [
    { id: 1, position: 1, account_number: "512000", account_label: "Banque", label: "Encaissement", debit: "10.00", credit: "0.00" },
    { id: 2, position: 2, account_number: "706000", account_label: "Loyers", label: "Loyer", debit: "0.00", credit: "10.00" },
  ],
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function queryMatches(query: string, width: number): boolean {
  return query.split(/\s+and\s+/i).every((part) => {
    const max = /max-width:\s*(\d+)px/.exec(part);
    if (max) return width <= Number(max[1]);
    const min = /min-width:\s*(\d+)px/.exec(part);
    if (min) return width >= Number(min[1]);
    return false;
  });
}

function installViewport(width: number) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: queryMatches(query, width),
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }));
}

function installAppFetch() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = String(url);
    if (path === "/api/dashboard") return json(dashboardFixture("ready"));
    if (path.includes("/api/ledger/setup")) {
      return json({ activity: { activity_name: "Fictif" }, years: [{ id: 1, year: 2025, start_date: "2025-01-01", end_date: "2025-12-31", status: "OPEN" }] });
    }
    if (path.includes("/api/ledger/accounts")) return json(accounts);
    if (path.includes("/api/ledger/journals")) return json([{ code: "OD", label: "Opérations", active: true }]);
    if (path.includes("/entries?")) return json({ entries: [journalEntry], count: 1 });
    if (path.endsWith("/balance")) {
      return json({
        balance: [{ account_number: "512000", label: "Banque", total_debit: "123.45", total_credit: "0.00", debit_balance: "123.45", credit_balance: "0.00" }],
        total_debit: "123.45",
        total_credit: "123.45",
        balanced: true,
      });
    }
    return json(ready);
  }));
}

function renderLedger(tab: "Brouillons" | "Journal" | "Balance" | "Plan comptable" = "Brouillons") {
  return renderWithRouter(<LedgerPage />, ledgerPath(tab), "/comptabilite/:tab");
}

describe("responsive layout", () => {
  beforeEach(() => {
    installAppFetch();
  });

  it("keeps the desktop navigation and tables", async () => {
    installViewport(1200);
    const shell = renderAt("/");
    expect(await screen.findByText("Prêt à vérifier")).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(nav).queryByRole("button", { name: /menu/i })).not.toBeInTheDocument();
    expect(within(nav).getAllByRole("link")).toHaveLength(navItems.length);
    expect(document.querySelector(".app-layout")).not.toHaveClass("narrow-controls");
    expect(screen.queryByRole("navigation", { name: "Sections de la comptabilité" })).not.toBeInTheDocument();
    shell.unmount();

    renderLedger("Balance");
    expect(await screen.findByRole("table")).toHaveTextContent("123,45");
    expect(document.querySelector("[data-mobile-variant='cards']")).not.toBeInTheDocument();
    expect(document.querySelector(".select-full-value")).not.toBeInTheDocument();
  });

  it.each(WIDTHS)("folds the mobile menu without removing navigation at %s px", async (width) => {
    installViewport(width);
    renderAt("/");
    expect(await screen.findByText("Prêt à vérifier")).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Navigation principale" });
    const toggle = within(nav).getByRole("button", { name: "Ouvrir le menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveAttribute("aria-controls", "primary-nav-links");
    expect(within(nav).getByRole("link", { name: /Vue/ })).toBeVisible();
    expect(within(nav).queryByRole("link", { name: /Comptabilité/ })).not.toBeInTheDocument();
    expect(document.querySelectorAll("#primary-nav-links a")).toHaveLength(navItems.length);

    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(within(nav).getByRole("link", { name: /Comptabilité/ })).toBeVisible();
    expect(within(nav).getAllByRole("link")).toHaveLength(navItems.length);

    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Ouvrir le menu" })).toHaveAttribute("aria-expanded", "false");
    expect(within(nav).getByRole("link", { name: /Vue/ })).toBeVisible();
    expect(document.querySelectorAll("#primary-nav-links a")).toHaveLength(navItems.length);

    await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));
    await userEvent.click(within(nav).getByRole("link", { name: /Comptabilité/ }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Ouvrir le menu" })).toHaveAttribute("aria-expanded", "false");
    });
    expect(screen.getByRole("navigation", { name: "Navigation principale" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Comptabilité/ })).toBeVisible();
  });

  it.each([320, 390] as const)("shows the full select value between 320 and 430 px (%s)", async (width) => {
    installViewport(width);
    const shell = renderAt("/");
    expect(await screen.findByText("Prêt à vérifier")).toBeInTheDocument();
    expect(document.querySelector(".app-layout")).toHaveClass("narrow-controls");
    shell.unmount();

    renderLedger();
    const select = await screen.findByRole("combobox", { name: "Exercice" });
    const chosen = select.querySelector("option:checked")?.textContent?.replace(/\s+/g, " ").trim();
    const full = select.parentElement?.querySelector(".select-full-value");
    expect(chosen && chosen.length).toBeGreaterThan(0);
    expect(full).toHaveTextContent(chosen ?? "");
    expect(select).toHaveAttribute("title", chosen);
  });

  it("does not repeat select values at 768 px", async () => {
    installViewport(768);
    renderAt("/");
    expect(await screen.findByText("Prêt à vérifier")).toBeInTheDocument();
    expect(document.querySelector(".app-layout")).not.toHaveClass("narrow-controls");
    renderLedger();
    expect(await screen.findByLabelText("Exercice")).toBeInTheDocument();
    expect(document.querySelector(".select-full-value")).not.toBeInTheDocument();
  });

  it.each(WIDTHS)("renders journal, balance, chart and anchors as mobile variants at %s px", async (width) => {
    installViewport(width);
    const journalView = renderLedger("Journal");
    expect(await screen.findByRole("navigation", { name: "Sections de la comptabilité" })).toBeInTheDocument();
    expect(document.getElementById("reglages-comptables")?.tagName).toBe("DETAILS");
    const journal = await screen.findByRole("list", { name: "Lignes de l’écriture" });
    expect(journal.closest("[data-mobile-variant]")).toHaveAttribute("data-mobile-variant", "cards");
    expect(journal.closest("[data-table]")).toHaveAttribute("data-table", "Lignes de l’écriture");
    expect(journal).toHaveTextContent("512000");
    expect(screen.getByText(/Colonnes principales : Compte, Débit €, Crédit €/)).toBeInTheDocument();
    expect(screen.getByText(/Équilibrée · Débit/)).toBeInTheDocument();
    journalView.unmount();

    const balanceView = renderLedger("Balance");
    const balance = await screen.findByRole("list", { name: "Balance générale" });
    expect(balance.closest("[data-mobile-variant]")).toHaveAttribute("data-mobile-variant", "cards");
    expect(balance).toHaveTextContent("123,45");
    expect(screen.getByText(/Balance équilibrée/)).toBeInTheDocument();
    expect(screen.getByText(/Colonnes principales : Compte, Libellé, Solde débiteur, Solde créditeur/)).toBeInTheDocument();
    balanceView.unmount();

    renderLedger("Plan comptable");
    const chart = await screen.findByRole("list", { name: "Plan comptable" });
    expect(chart).toHaveAttribute("data-mobile-variant", "cards");
    expect(screen.getByText(/Colonnes principales : numéro, libellé, nature et utilisation/)).toBeInTheDocument();
  });

  it.each(WIDTHS)("renders the depreciation schedule as cards at %s px", async (width) => {
    installViewport(width);
    const period = {
      id: 2, target_type: "ASSET", target_id: 2, target_label: "Mobilier", base: "1200.00",
      period_start: "2025-07-01", period_end: "2025-12-31", days: 184, amount: "120.92",
      accumulated: "120.92", net_book_value: "1079.08", status: "CALCULATED",
      accounting_entry_id: null, depreciation_account: "281840",
    };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      const path = String(url);
      if (path === "/api/ledger/setup") return json({ activity: { id: 1 }, years: [{ id: 1, year: 2025, status: "OPEN" }] });
      if (path === "/api/ledger/accounts") return json([]);
      if (path === "/api/operations/properties") return json([{ id: 1, name: "Bien fictif" }]);
      if (path === "/api/assets") return json([]);
      if (path.endsWith("/periods")) return json([period]);
      return json([]);
    }));
    renderWithRouter(<AssetsPage />, "/immobilisations", "/immobilisations");
    expect(await screen.findByRole("navigation", { name: "Sections des immobilisations" })).toBeInTheDocument();
    const schedule = await screen.findByRole("list", { name: "Dotations" });
    expect(schedule.closest("[data-mobile-variant]")).toHaveAttribute("data-mobile-variant", "cards");
    expect(schedule).toHaveTextContent("Mobilier");
    expect(schedule).toHaveTextContent("Comptabiliser");
    expect(screen.getByText(/Colonnes principales : Actif \/ composant, Dotation, État/)).toBeInTheDocument();
    expect(screen.getByText(/Autres colonnes : Période, Jours, Cumul, VNC de la base/)).toBeInTheDocument();
  });

  it.each(WIDTHS)("renders the import preview as cards at %s px", async (width) => {
    installViewport(width);
    const preview = {
      profile: "bank",
      ready: true,
      delimiter: ";",
      headers: ["Date", "Libellé", "Montant"],
      fields: [
        { key: "date", label: "Date", required: true, help: "" },
        { key: "label", label: "Libellé", required: true, help: "" },
        { key: "amount", label: "Montant", required: true, help: "" },
      ],
      mapping: { date: "Date", label: "Libellé", amount: "Montant" },
      issues: [],
      rows: [{
        line: 2,
        status: "valid",
        importable: true,
        duplicate: false,
        display: { date: "01/03/2025", label: "Loyer", amount: "10,00" },
        issues: [],
        warnings: [],
        suggested_account: "512000",
      }],
      summary: { valid: 1, duplicate: 0, warning: 0, error: 0, count: 1, importable: 1 },
      rejects_csv: "",
      loan_reference: null,
      imported: 0,
    };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      const path = String(url);
      if (path.endsWith("/imports/inspect")) {
        return json({
          delimiter: ";",
          headers: ["Date", "Libellé", "Montant"],
          fields: { bank: preview.fields, operations: [], loan_payments: [] },
          suggestions: { bank: preview.mapping, operations: {}, loan_payments: {} },
        });
      }
      if (path.endsWith("/imports/bank/preview")) return json(preview);
      return json({});
    }));
    renderWithRouter(
      <CsvImportAssistant
        profile="bank"
        summaryTitle="Importer un relevé CSV"
        intro="Collez un relevé."
        contentLabel="Contenu CSV"
        textareaId="import-releve"
        anchor="/operations/banque#import-releve"
        causeId="bank-preview-causes"
        postCauseId="bank-post-causes"
        previewLabel="Prévisualiser l’import"
        commitLabel="Confirmer l’import des mouvements"
        busy={false}
        action={(fn) => { void fn(); }}
        context={{ bank_account_id: 1 }}
        onImported={() => undefined}
      />,
      "/operations/banque",
      "/operations/banque",
    );
    await userEvent.click(screen.getByText("Importer un relevé CSV"));
    await userEvent.type(screen.getByLabelText("Contenu CSV"), "Date;Libellé;Montant\n01/03/2025;Loyer;10,00");
    await userEvent.click(await screen.findByRole("button", { name: "Prévisualiser l’import" }));
    const cards = await screen.findByRole("list", { name: "Aperçu de l’import" });
    expect(cards.closest("[data-mobile-variant]")).toHaveAttribute("data-mobile-variant", "cards");
    expect(cards).toHaveTextContent("Valide");
    expect(cards).toHaveTextContent("Loyer");
    expect(screen.getByText(/Colonnes principales : Ligne, Statut, Détail/)).toBeInTheDocument();
  });

  it("keeps chart rows on desktop", () => {
    installViewport(1200);
    renderWithRouter(
      <ChartOfAccounts
        accounts={accounts}
        busy={false}
        notice={null}
        onDismiss={() => undefined}
        onCreate={() => undefined}
        onToggle={() => undefined}
      />,
      "/plan",
      "/plan",
    );
    expect(screen.getByRole("list", { name: "Plan comptable" })).not.toHaveAttribute("data-mobile-variant");
    expect(screen.queryByText(/Colonnes principales : numéro/)).not.toBeInTheDocument();
  });

  it("declares narrow control rules and the mobile menu breakpoint", () => {
    const css = readFileSync("src/style.css", "utf8");
    const narrow = css.slice(css.indexOf("@media(max-width:430px)"));
    expect(narrow).toContain("text-overflow:clip");
    expect(narrow).toContain("max-width:100%");
    expect(narrow).toContain("white-space:normal");
    expect(css).toContain("@media(max-width:768px)");
    expect(css).toContain(".nav-toggle");
  });
});
