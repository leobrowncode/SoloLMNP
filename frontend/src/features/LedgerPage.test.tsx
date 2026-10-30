import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ledgerPath } from "../routing/paths";
import { renderWithRouter } from "../routing/testPage";
import LedgerPage from "./LedgerPage";
import { cents, amount } from "../api/ledger";
import { YEAR_END_BEFORE_START } from "../lib/format";

const accounts = [
  { number: "512000", label: "Banque", active: true, account_type: "ASSET" },
  { number: "706000", label: "Prestations", active: true, account_type: "INCOME" },
];
function mockApi() {
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    const path = url.replace("/api/ledger", "");
    let data: unknown = {};
    if (path === "/setup") data = { activity: { activity_name: "Fictif" }, years: [{ id: 1, year: 2025, start_date: "2025-01-01", end_date: "2025-12-31", status: "OPEN" }] };
    if (path === "/accounts") data = accounts;
    if (path === "/journals") data = [{ code: "OD", label: "Opérations", active: true }];
    if (path.startsWith("/entries?")) data = { entries: [], count: 0 };
    if (path === "/entries" && init?.method === "POST") data = { id: 1 };
    if (path.endsWith("/balance")) data = { balance: [{ account_number: "512000", label: "Banque", total_debit: "123.45", total_credit: "0.00", debit_balance: "123.45", credit_balance: "0.00" }], total_debit: "123.45", total_credit: "123.45", balanced: true };
    return new Response(JSON.stringify(data), { status: 200 });
  });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}
function renderLedger(tab: "Brouillons" | "Journal" | "Balance" = "Brouillons") {
  return renderWithRouter(<LedgerPage />, ledgerPath(tab), "/comptabilite/:tab");
}
describe("ledger", () => {
  it("preserves exact cents beyond JavaScript safe integer range", () => {
    expect(amount(cents("90071992547409,91") + cents("0.09"))).toBe("90071992547410.00");
    for (const invalid of ["NaN", "-1", "0.001", "", "1e4"]) expect(() => cents(invalid)).toThrow();
  });
  it("saves decimal strings and requires a distinct validation action", async () => {
    const fetcher = mockApi();
    renderLedger();
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
    await userEvent.clear(debit); await userEvent.type(debit, "123,45");
    await userEvent.clear(credit); await userEvent.type(credit, "123.45");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer le brouillon" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Brouillon enregistré"));
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(/Écriture “Test” enregistrée à \d{2}:\d{2}/);
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).not.toHaveFocus();
    expect(document.getElementById("ecriture-saisie")).toHaveClass("save-highlight");
    const call = fetcher.mock.calls.find(([url, init]) => url === "/api/ledger/entries" && init?.method === "POST");
    expect(JSON.parse(String(call?.[1]?.body)).lines[0].debit).toBe("123.45");
    expect(fetcher.mock.calls.some(([url]) => url.endsWith("/validate"))).toBe(false);
  });
  it("loads the balance from the ledger API", async () => {
    mockApi(); renderLedger("Balance");
    expect(await screen.findByText("Balance équilibrée")).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveTextContent("123,45");
  });
  it("searches journal entries and resets a miss without showing the empty journal", async () => {
    const posted = {
      id: 3, version: 1, fiscal_year_id: 1, journal_code: "OD", accounting_date: "2025-02-01",
      piece_date: "2025-02-01", piece_reference: "LOY-1", label: "Loyer février", status: "VALIDATED",
      entry_number: "2025-000003", total_debit: "10.00", total_credit: "10.00", balanced: true,
      reversal_of_id: null, source_type: "REVENUE",
      lines: [{ id: 1, position: 1, account_number: "512000", account_label: "Banque", label: "Encaissement", debit: "10.00", credit: "0.00" }],
    };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      const path = String(url);
      if (path.endsWith("/setup")) {
        return new Response(JSON.stringify({
          activity: { activity_name: "Fictif" },
          years: [{ id: 1, year: 2025, start_date: "2025-01-01", end_date: "2025-12-31", status: "OPEN" }],
        }), { status: 200 });
      }
      if (path.endsWith("/accounts")) return new Response(JSON.stringify(accounts), { status: 200 });
      if (path.endsWith("/journals")) return new Response(JSON.stringify([{ code: "OD", label: "Opérations", active: true }]), { status: 200 });
      if (path.includes("/entries?")) return new Response(JSON.stringify({ entries: [posted], count: 1 }), { status: 200 });
      return new Response("{}", { status: 200 });
    }));
    const user = userEvent.setup();
    renderLedger("Journal");
    expect(await screen.findByRole("heading", { name: /Loyer février/ })).toBeInTheDocument();
    expect(screen.queryByText("Aucune écriture pour cette vue.")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Rechercher une écriture"), "zzzz");
    expect(screen.getByText("Aucun résultat")).toBeInTheDocument();
    expect(screen.queryByText("Aucune écriture pour cette vue.")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Loyer février/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Réinitialiser les filtres" }));
    expect(screen.getByRole("heading", { name: /Loyer février/ })).toBeInTheDocument();
  });

  it("filters generated and business entries with readable source choices", async () => {
    const fetcher = mockApi(); renderLedger("Journal");
    const source = await screen.findByRole("combobox", { name: "Source" });
    for (const value of ["DEPRECIATION", "OPENING", "INVENTORY", "SETTLEMENT", ""]) {
      await userEvent.selectOptions(source, value);
      await waitFor(() => {
        const calls = fetcher.mock.calls.filter(([url]) => url.includes("/entries?"));
        const params = new URLSearchParams(calls.at(-1)![0].split("?")[1]);
        expect(params.get("source")).toBe(value || null);
        expect(params.get("status")).toBe("VALIDATED");
        expect(params.get("offset")).toBe("0");
      });
    }
    expect(screen.getByRole("option", { name: "À-nouveaux" })).toHaveValue("OPENING");
    expect(screen.getByRole("option", { name: "Dotations aux amortissements" })).toHaveValue("DEPRECIATION");
  });
  it("shows network errors without claiming readiness", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Hors ligne")));
    renderLedger();
    expect(await screen.findByRole("alert")).toHaveTextContent("Hors ligne");
    expect(screen.queryByText("Balance équilibrée")).not.toBeInTheDocument();
    expect(screen.queryByText(/Chargement de la comptabilité/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Initialiser votre activité" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });
  it("recovers from an initial failure and distinguishes an empty journal from a read error", async () => {
    let setupFailed = true;
    let entriesFailed = false;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      const path = String(url);
      if (setupFailed && path.endsWith("/setup")) throw new Error("Hors ligne");
      if (path.endsWith("/setup")) {
        return new Response(JSON.stringify({
          activity: { activity_name: "Fictif" },
          years: [{ id: 1, year: 2025, start_date: "2025-01-01", end_date: "2025-12-31", status: "OPEN" }],
        }), { status: 200 });
      }
      if (path.endsWith("/accounts")) return new Response(JSON.stringify(accounts), { status: 200 });
      if (path.endsWith("/journals")) return new Response(JSON.stringify([{ code: "OD", label: "Opérations", active: true }]), { status: 200 });
      if (path.includes("/entries?")) {
        if (entriesFailed) return new Response(JSON.stringify({ detail: { code: "LEDGER_OFFLINE", message: "Journal illisible" } }), { status: 503 });
        return new Response(JSON.stringify({ entries: [], count: 0 }), { status: 200 });
      }
      return new Response("{}", { status: 200 });
    }));
    renderLedger();
    expect(await screen.findByRole("alert")).toHaveTextContent("Hors ligne");
    setupFailed = false;
    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(await screen.findByRole("button", { name: "Nouvelle écriture" })).toBeInTheDocument();
    expect(await screen.findByText(/Aucune écriture pour cette vue/)).toBeInTheDocument();
    entriesFailed = true;
    await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Source" }), "MANUAL");
    expect(await screen.findByRole("alert")).toHaveTextContent("Journal illisible");
    expect(screen.queryByText(/Chargement…/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Aucune écriture pour cette vue/)).not.toBeInTheDocument();
  });

  it("explains a closed exercise on a new entry and an unbalanced draft", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      const path = String(url);
      if (path.endsWith("/setup")) {
        return new Response(JSON.stringify({
          activity: { activity_name: "Fictif" },
          years: [{ id: 1, year: 2025, start_date: "2025-01-01", end_date: "2025-12-31", status: "CLOSED" }],
        }), { status: 200 });
      }
      if (path.endsWith("/accounts")) return new Response(JSON.stringify(accounts), { status: 200 });
      if (path.endsWith("/journals")) return new Response(JSON.stringify([{ code: "OD", label: "Opérations", active: true }]), { status: 200 });
      if (path.includes("/entries?")) {
        return new Response(JSON.stringify({
          entries: [{
            id: 7, version: 1, status: "DRAFT", entry_number: null, journal_code: "OD",
            accounting_date: "2025-01-02", piece_date: "2025-01-02", piece_reference: "B",
            label: "Déséquilibrée", fiscal_year_id: 1, balanced: false, reversal_of_id: null,
            total_debit: "1.00", total_credit: "0.00",
            lines: [{ account_number: "512000", label: "Banque", debit: "1.00", credit: "0.00" }],
          }, {
            id: 8, version: 1, status: "VALIDATED", entry_number: "2025-1", journal_code: "OD",
            accounting_date: "2025-01-03", piece_date: "2025-01-03", piece_reference: "E",
            label: "Extourne", fiscal_year_id: 1, balanced: true, reversal_of_id: 4,
            total_debit: "1.00", total_credit: "1.00", lines: [],
          }],
          count: 2,
        }), { status: 200 });
      }
      return new Response("{}", { status: 200 });
    }));
    renderLedger();
    const create = await screen.findByRole("button", { name: "Nouvelle écriture" });
    expect(create).toBeDisabled();
    expect(create).toHaveAttribute("aria-describedby", "ledger-year-causes");
    expect(document.getElementById("ledger-year-causes")).toHaveTextContent("clôturé");
    expect(document.querySelector('a[href="/fiscalite#reopen-title"]')).toHaveTextContent("Réouvrir l’exercice");
    const validate = await screen.findByRole("button", { name: "Valider" });
    expect(validate).toBeDisabled();
    expect(validate).toHaveAttribute("aria-describedby", expect.stringContaining("entry-7-balance"));
    expect(document.getElementById("entry-7-balance")).toHaveTextContent("n’est pas équilibrée");
    await userEvent.click(screen.getByRole("button", { name: "Journal" }));
    const reverse = await screen.findByRole("button", { name: "Extourner" });
    expect(reverse).toBeDisabled();
    expect(document.getElementById("entry-8-reversal")).toHaveTextContent("déjà une extourne");
    expect(document.querySelector('a[href="/comptabilite/journal"]')).toHaveTextContent("Consulter le journal");
  });

  it("explains an exercise whose end date is before its start", async () => {
    const fetcher = mockApi();
    fetcher.mockImplementation(async (url: string) => {
      const path = String(url).replace("/api/ledger", "");
      if (path === "/setup") {
        return new Response(JSON.stringify({
          activity: { activity_name: "Fictif" },
          years: [],
        }), { status: 200 });
      }
      if (path === "/accounts") return new Response(JSON.stringify(accounts), { status: 200 });
      if (path === "/journals") return new Response(JSON.stringify([{ code: "OD", label: "Opérations", active: true }]), { status: 200 });
      return new Response("{}", { status: 200 });
    });
    renderLedger();
    expect(await screen.findByRole("button", { name: "Créer l’exercice" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Début de l’exercice/), { target: { value: "2025-12-31" } });
    fireEvent.change(screen.getByLabelText(/Fin de l’exercice/), { target: { value: "2025-01-01" } });
    fireEvent.change(screen.getByLabelText("Millésime fiscal"), { target: { value: "2025" } });
    fireEvent.click(screen.getByRole("button", { name: "Créer l’exercice" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(YEAR_END_BEFORE_START);
    expect(fetcher.mock.calls.some(([url, init]) => String(url).endsWith("/years") && (init as RequestInit | undefined)?.method === "POST")).toBe(false);
  });
});
