import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { dashboardFixture } from "../features/dashboardFixture";
import type { Statements } from "../features/StatementsPage";
import { ledgerPath, navItems, operationsPath, ROUTES, viewDocumentTitle } from "./paths";
import { renderAt } from "./renderTestApp";
import { createTestRouter } from "./router";

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

const setup = {
  activity: { activity_name: "Test", siren: "123456789", siret: null },
  years: [{ id: 1, year: 2026, start_date: "2026-01-01", end_date: "2026-12-31", status: "OPEN" }],
};

const accounts = [
  { number: "512000", label: "Banque", active: true, account_type: "ASSET" },
  { number: "706000", label: "Loyers", active: true, account_type: "INCOME" },
];

const journals = [{ code: "OD", label: "Opérations", active: true }];

function statements(): Statements {
  return {
    fiscal_year_id: 1,
    start_date: "2026-01-01",
    end_date: "2026-12-31",
    excluded_draft_count: 0,
    income_statement: { income: [], expenses: [], total_income: "0.00", total_expenses: "0.00", result: "0.00" },
    balance_sheet: {
      assets: [],
      liabilities: [],
      equity: [],
      total_assets: "0.00",
      total_liabilities: "0.00",
      total_equity: "0.00",
      current_result: "0.00",
      total_liabilities_and_equity: "0.00",
    },
  };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function payload(url: string, method: string): { status: number; body: unknown } {
  if (url.includes("/api/status")) return { status: 200, body: ready };
  if (url.includes("/api/dashboard")) return { status: 200, body: dashboardFixture("ready") };
  if (url.endsWith("/setup")) return { status: 200, body: setup };
  if (url.endsWith("/accounts")) return { status: 200, body: accounts };
  if (url.endsWith("/journals")) return { status: 200, body: journals };
  if (url.endsWith("/properties") || url.endsWith("/banks") || url.endsWith("/loans") || url.includes("/tenants")) {
    return { status: 200, body: [] };
  }
  if (url.includes("/entries") && method === "POST") return { status: 200, body: { id: 1 } };
  if (url.includes("/entries")) return { status: 200, body: { entries: [], count: 0 } };
  if (url.includes("/documents")) return { status: 200, body: { documents: [] } };
  if (url.includes("/backups")) return { status: 200, body: { backups: [] } };
  if (url.includes("/vintages")) return { status: 200, body: { vintages: [] } };
  if (url.includes("/statements")) return { status: 200, body: statements() };
  if (url.includes("/exports")) return { status: 200, body: { exports: {} } };
  if (url.includes("/api/assets") || url.includes("/api/operations")) return { status: 200, body: [] };
  return { status: 404, body: { detail: { code: "NOT_FOUND", message: "Absent pour ce test." } } };
}

function mockApi() {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const result = payload(String(input), init?.method ?? "GET");
    return json(result.body, result.status);
  }));
}

function headingLevels(): number[] {
  return [...document.querySelectorAll("h1, h2, h3, h4, h5, h6")].map((node) => Number(node.tagName.slice(1)));
}

function expectSingleH1(title: string) {
  const headings = screen.getAllByRole("heading");
  const h1s = headings.filter((node) => node.tagName === "H1");
  expect(h1s).toHaveLength(1);
  expect(h1s[0]).toHaveAccessibleName(title);
  expect(h1s[0]).toHaveAttribute("tabindex", "-1");
  const levels = headingLevels();
  expect(levels[0]).toBe(1);
  for (let index = 1; index < levels.length; index += 1) {
    const previous = levels[index - 1] ?? 0;
    const next = levels[index] ?? 0;
    expect(next, `niveaux ${levels.join(" > ")}`).toBeLessThanOrEqual(previous + 1);
  }
  expect(levels.some((level) => level > 3)).toBe(false);
  const brand = screen.getByRole("link", { name: "SoloLMNP — accueil" });
  expect(brand.tagName).toBe("A");
  expect(within(brand).queryByRole("heading")).not.toBeInTheDocument();
  expect(document.getElementById("route-announcement")).toHaveTextContent(title);
  expect(document.getElementById("route-announcement")).toHaveAttribute("aria-live", "polite");
  expect(document.title).toBe(viewDocumentTitle(title));
}

const routes: { path: string; title: string; ready: RegExp | string }[] = [
  { path: ROUTES.home, title: "Vue d’ensemble", ready: "Tableau de bord du dossier" },
  { path: ledgerPath(), title: "Comptabilité", ready: "Identité pour la liasse" },
  { path: operationsPath(), title: "Opérations & banque", ready: "Opérations et banque" },
  { path: ROUTES.assets, title: "Immobilisations", ready: "Dotations comptables" },
  { path: ROUTES.statements, title: "États comptables", ready: "Compte de résultat" },
  { path: ROUTES.fiscal, title: "Fiscalité LMNP", ready: "Liasse" },
  { path: ROUTES.conservation, title: "Conservation", ready: "Restauration" },
];

afterEach(() => {
  document.title = "";
});

describe("hiérarchie des titres", () => {
  it.each(routes)("$title a un seul h1 et ne saute pas de niveau", async ({ path, title, ready: marker }) => {
    mockApi();
    renderAt(path);
    await screen.findByRole("heading", { name: marker });
    expectSingleH1(title);
    expect(navItems.map((item) => item.label)).toContain(title);
  });

  it("annonce le titre et place le focus sur le h1 au changement de vue", async () => {
    mockApi();
    renderAt(ROUTES.home);
    const home = await screen.findByRole("heading", { level: 1, name: "Vue d’ensemble" });
    await waitFor(() => expect(home).toHaveFocus());
    expect(document.title).toBe(viewDocumentTitle("Vue d’ensemble"));

    await userEvent.click(screen.getByRole("link", { name: "Comptabilité" }));
    const ledger = await screen.findByRole("heading", { level: 1, name: "Comptabilité" });
    await waitFor(() => expect(ledger).toHaveFocus());
    expect(document.getElementById("route-announcement")).toHaveTextContent("Comptabilité");
    expect(document.title).toBe(viewDocumentTitle("Comptabilité"));
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);

    await userEvent.click(screen.getByRole("link", { name: "Fiscalité LMNP" }));
    const fiscal = await screen.findByRole("heading", { level: 1, name: "Fiscalité LMNP" });
    await waitFor(() => expect(fiscal).toHaveFocus());
    expect(document.getElementById("route-announcement")).toHaveTextContent("Fiscalité LMNP");
    expect(document.title).toBe(viewDocumentTitle("Fiscalité LMNP"));
  });

  it("garde le focus sur l’ancre et sur l’onglet, sans réécrire l’annonce d’enregistrement", async () => {
    mockApi();
    const router = createTestRouter([ledgerPath()]);
    render(<RouterProvider router={router} />);
    await screen.findByRole("heading", { name: "Identité pour la liasse" });
    await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Comptabilité" })).toHaveFocus());

    await router.navigate(`${ledgerPath()}#identite-liasse`);
    await waitFor(() => expect(document.getElementById("identite-liasse")).toHaveFocus());
    expect(document.getElementById("route-announcement")).toHaveTextContent("Comptabilité");
    expect(document.title).toBe(viewDocumentTitle("Comptabilité"));
    expect(screen.getByRole("heading", { level: 1 })).not.toHaveFocus();

    await userEvent.click(screen.getByRole("button", { name: "Journal" }));
    expect(screen.getByRole("button", { name: "Journal" })).toHaveFocus();
    expect(document.getElementById("route-announcement")).toHaveTextContent("Comptabilité");

    await userEvent.click(screen.getByRole("button", { name: "Brouillons" }));
    await userEvent.click(await screen.findByRole("button", { name: "Nouvelle écriture" }));
    await userEvent.type(screen.getByLabelText("Référence de la pièce"), "TEST-1");
    await userEvent.type(screen.getByLabelText("Libellé de l’écriture"), "Test");
    const selectors = screen.getAllByLabelText("Compte");
    await userEvent.selectOptions(selectors[0]!, "512000");
    await userEvent.selectOptions(selectors[1]!, "706000");
    const labels = screen.getAllByLabelText("Libellé");
    await userEvent.type(labels[0]!, "Banque");
    await userEvent.type(labels[1]!, "Produit");
    const debit = screen.getAllByLabelText("Débit (€)")[0]!;
    const credit = screen.getAllByLabelText("Crédit (€)")[1]!;
    await userEvent.clear(debit);
    await userEvent.type(debit, "123,45");
    await userEvent.clear(credit);
    await userEvent.type(credit, "123,45");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer le brouillon" }));

    const status = await screen.findByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent(/Écriture “Test” enregistrée à \d{2}:\d{2}/);
    expect(status).not.toHaveFocus();
    expect(document.getElementById("page-title")).not.toHaveFocus();
    expect(document.getElementById("route-announcement")).toHaveTextContent("Comptabilité");
    expect(document.getElementById("route-announcement")).not.toHaveTextContent("enregistrée");
    expect(screen.getAllByRole("status")).toHaveLength(1);
  });
});
