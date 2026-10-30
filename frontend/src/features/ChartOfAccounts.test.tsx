import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ledgerPath } from "../routing/paths";
import { renderWithRouter } from "../routing/testPage";
import { ACCOUNT_NATURES, ACCOUNT_TYPES } from "./accountNature";
import ChartOfAccounts from "./ChartOfAccounts";
import LedgerPage from "./LedgerPage";

const accounts = [
  { number: "211000", label: "Terrain", active: false, account_type: "ASSET" },
  { number: "164000", label: "Emprunt", active: true, account_type: "LIABILITY" },
  { number: "108000", label: "Exploitant", active: true, account_type: "EQUITY" },
  { number: "615000", label: "Entretien", active: true, account_type: "EXPENSE" },
  { number: "706000", label: "Loyers", active: false, account_type: "INCOME" },
  { number: "199000", label: "Inconnu", active: true, account_type: "PASSIF" },
];

function optionPairs(select: HTMLElement): string[][] {
  return [...select.querySelectorAll("option")].map((option) => [option.value, option.textContent ?? ""]);
}

function renderChart() {
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url).replace("/api/ledger", "");
    let data: unknown = {};
    if (path === "/setup") {
      data = {
        activity: { activity_name: "Fictif" },
        years: [{ id: 1, year: 2026, start_date: "2026-01-01", end_date: "2026-12-31", status: "OPEN" }],
      };
    }
    if (path === "/accounts" && init?.method !== "POST") data = accounts;
    if (path === "/accounts" && init?.method === "POST") data = { number: "164100", label: "Second emprunt", account_type: "LIABILITY", active: true };
    if (path === "/journals") data = [{ code: "OD", label: "Opérations", active: true }];
    if (path.startsWith("/entries?")) data = { entries: [], count: 0 };
    if (path.endsWith("/active")) data = { number: "164000", active: false };
    return new Response(JSON.stringify(data), { status: 200 });
  });
  vi.stubGlobal("fetch", fetcher);
  renderWithRouter(<LedgerPage />, ledgerPath("Plan comptable"), "/comptabilite/:tab");
  return fetcher;
}

function row(number: string): HTMLElement {
  return screen.getByRole("listitem", { name: new RegExp(number) });
}

describe("chart of accounts", () => {
  it("shows the five natures and both usage states separately", async () => {
    renderChart();
    expect(await screen.findByRole("list", { name: "Plan comptable" })).toBeInTheDocument();

    const asset = row("211000");
    expect(asset).toHaveTextContent("Actif");
    expect(asset).toHaveTextContent("Inactif");
    expect(asset).not.toHaveTextContent("Activé");

    const loan = row("164000");
    expect(loan).toHaveTextContent("Dette");
    expect(loan).toHaveTextContent("Activé");
    expect(loan).not.toHaveTextContent("Actif");

    expect(row("108000")).toHaveTextContent("Capitaux");
    expect(row("108000")).toHaveTextContent("Activé");
    expect(row("615000")).toHaveTextContent("Charge");
    expect(row("615000")).toHaveTextContent("Activé");
    expect(row("615000")).not.toHaveTextContent("Actif");
    expect(row("706000")).toHaveTextContent("Produit");
    expect(row("706000")).toHaveTextContent("Inactif");
    expect(row("199000")).toHaveTextContent("PASSIF");
    expect(row("199000")).toHaveTextContent("Activé");
    expect(row("199000")).not.toHaveTextContent("Actif");
  });

  it("keeps the five natures in the filter and the create form", async () => {
    const user = userEvent.setup();
    const fetcher = renderChart();
    const formNature = await screen.findByRole("combobox", { name: "Nature" });
    const natureFilter = screen.getByRole("combobox", { name: "Filtrer par nature" });
    const usageFilter = screen.getByRole("combobox", { name: "Filtrer par utilisation" });
    const natures = ACCOUNT_TYPES.map((type) => [type, ACCOUNT_NATURES[type]]);

    expect(optionPairs(formNature)).toEqual(natures);
    expect(optionPairs(natureFilter)).toEqual([["", "Toutes les natures"], ...natures]);
    expect(optionPairs(usageFilter)).toEqual([
      ["", "Tous les états"],
      ["active", "Activé"],
      ["inactive", "Inactif"],
    ]);
    expect(within(formNature).queryByRole("option", { name: "Activé" })).not.toBeInTheDocument();
    expect(within(formNature).queryByRole("option", { name: "Inactif" })).not.toBeInTheDocument();
    expect(within(usageFilter).queryByRole("option", { name: "Actif" })).not.toBeInTheDocument();
    expect(within(usageFilter).queryByRole("option", { name: "Dette" })).not.toBeInTheDocument();

    await user.selectOptions(natureFilter, "LIABILITY");
    expect(row("164000")).toHaveTextContent("Dette");
    expect(screen.queryByRole("listitem", { name: /615000/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("listitem", { name: /211000/ })).not.toBeInTheDocument();
    expect(optionPairs(formNature)).toEqual(natures);

    await user.selectOptions(usageFilter, "inactive");
    expect(screen.getByText("Aucun compte pour cette nature ou cette utilisation.")).toBeInTheDocument();
    expect(optionPairs(formNature)).toEqual(natures);

    await user.selectOptions(natureFilter, "");
    expect(row("211000")).toHaveTextContent("Inactif");
    expect(row("706000")).toHaveTextContent("Produit");
    expect(screen.queryByRole("listitem", { name: /164000/ })).not.toBeInTheDocument();

    await user.selectOptions(formNature, "LIABILITY");
    await user.type(screen.getByLabelText("Numéro"), "164100");
    await user.type(screen.getByLabelText("Libellé du compte"), "Second emprunt");
    await user.click(screen.getByRole("button", { name: "Ajouter le compte" }));
    await waitFor(() => {
      const call = fetcher.mock.calls.find(([url, init]) => String(url).endsWith("/accounts") && init?.method === "POST");
      expect(JSON.parse(String(call?.[1]?.body))).toEqual({
        number: "164100",
        label: "Second emprunt",
        account_type: "LIABILITY",
      });
    });
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(/Compte “164100 Second emprunt” créé à \d{2}:\d{2}/);
    expect(status).not.toHaveFocus();
    expect(document.getElementById("ajouter-compte")).toHaveClass("save-highlight");
  });

  it("explains an empty chart and resets a search that matches nothing", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <ChartOfAccounts accounts={[]} busy={false} notice={null} onDismiss={() => undefined} onCreate={() => undefined} onToggle={() => undefined} />,
    );
    expect(screen.getByText("Aucun compte dans le plan.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Renseigner le formulaire" })).toHaveAttribute("href", "#ajouter-compte");
    expect(screen.queryByText("Aucun compte pour cette nature ou cette utilisation.")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Réinitialiser les filtres" })).not.toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Plan comptable" })).not.toBeInTheDocument();

    rerender(
      <ChartOfAccounts accounts={accounts} busy={false} notice={null} onDismiss={() => undefined} onCreate={() => undefined} onToggle={() => undefined} />,
    );
    expect(screen.getByRole("list", { name: "Plan comptable" })).toBeInTheDocument();
    expect(screen.getAllByText("Actif").length).toBeGreaterThan(0);
    await user.type(screen.getByLabelText("Rechercher un compte"), "zzzz");
    expect(screen.getByText("Aucun résultat")).toBeInTheDocument();
    expect(screen.getByText("Aucun compte ne correspond à cette recherche.")).toBeInTheDocument();
    expect(screen.queryByText("Aucun compte dans le plan.")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Réinitialiser les filtres" }));
    expect(screen.getByRole("listitem", { name: /164000/ })).toBeInTheDocument();
    expect(screen.queryByText("Aucun résultat")).not.toBeInTheDocument();
  });

  it("opens the nature glossary from the chart", async () => {
    const user = userEvent.setup();
    renderChart();
    await user.click(await screen.findByRole("button", { name: "Aide : Nature du compte" }));
    expect(screen.getByRole("tooltip")).toHaveTextContent("Activé ou Inactif");
    expect(screen.getByRole("tooltip")).toHaveTextContent("Dette");
  });
});
