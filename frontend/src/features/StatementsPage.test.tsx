import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import StatementsPage, { type Statements } from "./StatementsPage";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const setup = { activity: {}, years: [{ id: 1, year: 2025 }, { id: 2, year: 2026 }] };
function report(year: number): Statements {
  return {
    fiscal_year_id: year, start_date: `${2024 + year}-01-01`, end_date: `${2024 + year}-12-31`, excluded_draft_count: 1,
    income_statement: { income: [], expenses: [], total_income: "0.00", total_expenses: "10.01", result: "-10.01" },
    balance_sheet: { assets: [], liabilities: [], equity: [], total_assets: "0.00", total_liabilities: "10.01", total_equity: "0.00", current_result: "-10.01", total_liabilities_and_equity: "0.00" },
  };
}
afterEach(() => vi.restoreAllMocks());

test("shows provisional statements and removes stale totals on refresh failure", async () => {
  let failed = false;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => String(input).endsWith("/setup") ? response(setup) : failed ? response({ detail: { message: "Ledger déséquilibré" } }, 409) : response(report(1)));
  render(<StatementsPage />);
  expect(await screen.findByText("Résultat comptable : -10.01 €")).toBeInTheDocument();
  expect(screen.getByText(/Brouillons exclus : 1/)).toBeInTheDocument();
  failed = true;
  fireEvent.click(screen.getByRole("button", { name: "Actualiser les états" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Ledger déséquilibré");
  expect(screen.queryByText("Résultat comptable : -10.01 €")).not.toBeInTheDocument();
});

test("ignores late responses from the previous year", async () => {
  let finish: ((value: Response) => void) | undefined;
  const pending = new Promise<Response>((resolve) => { finish = resolve; });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/setup")) return response(setup);
    if (url.includes("/years/1/")) return pending;
    return response(report(2));
  });
  render(<StatementsPage />);
  fireEvent.change(await screen.findByLabelText("Exercice"), { target: { value: "2" } });
  expect(await screen.findByText(/2026-01-01 — 2026-12-31/)).toBeInTheDocument();
  await act(async () => { finish?.(response(report(1))); await pending; });
  await waitFor(() => expect(screen.queryByText(/2025-01-01 — 2025-12-31/)).not.toBeInTheDocument());
});

test("explains how to start without an exercise", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ activity: null, years: [] }));
  render(<StatementsPage />);
  expect(await screen.findByText(/Créez un exercice/)).toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});
