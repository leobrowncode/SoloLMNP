import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import LedgerPage from "./LedgerPage";
import { cents, amount } from "../api/ledger";

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
describe("ledger", () => {
  it("preserves exact cents beyond JavaScript safe integer range", () => {
    expect(amount(cents("90071992547409,91") + cents("0.09"))).toBe("90071992547410.00");
    for (const invalid of ["NaN", "-1", "0.001", "", "1e4"]) expect(() => cents(invalid)).toThrow();
  });
  it("saves decimal strings and requires a distinct validation action", async () => {
    const fetcher = mockApi();
    render(<LedgerPage />);
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
    const call = fetcher.mock.calls.find(([url, init]) => url === "/api/ledger/entries" && init?.method === "POST");
    expect(JSON.parse(String(call?.[1]?.body)).lines[0].debit).toBe("123.45");
    expect(fetcher.mock.calls.some(([url]) => url.endsWith("/validate"))).toBe(false);
  });
  it("loads the balance from the ledger API", async () => {
    mockApi(); render(<LedgerPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Balance" }));
    expect(await screen.findByText("Balance équilibrée")).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveTextContent("123.45");
  });
  it("filters generated and business entries with readable source choices", async () => {
    const fetcher = mockApi(); render(<LedgerPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Journal" }));
    const source = screen.getByRole("combobox", { name: "Source" });
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
    render(<LedgerPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Hors ligne");
    expect(screen.queryByText("Balance équilibrée")).not.toBeInTheDocument();
  });
});
