import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import AssetsPage from "./AssetsPage";

const json = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } }));

afterEach(() => vi.restoreAllMocks());

test("shows protected land and calculates a midyear depreciation period", async () => {
  const calls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input); calls.push(url);
    if (url === "/api/ledger/setup") return json({ activity: { id: 1 }, years: [{ id: 1, year: 2025, start_date: "2025-01-01", end_date: "2025-12-31", status: "OPEN" }] });
    if (url === "/api/ledger/accounts") return json([]);
    if (url === "/api/operations/properties") return json([{ id: 1, name: "Bien fictif" }]);
    if (url === "/api/assets") return json([{ id: 1, property_id: 1, category: "LAND", label: "Terrain fictif", acquisition_value: "20000.00", depreciable_value: "0.00", non_depreciable_value: "20000.00", residual_value: "0.00", useful_life_months: null, method: "NONE", asset_account: "211000", depreciation_account: null, components: [] }]);
    if (url === "/api/assets/years/1/periods") return json([]);
    if (url === "/api/assets/years/1/calculate") return json([{ id: 2, target_type: "ASSET", target_id: 2, target_label: "Mobilier", base: "1200.00", period_start: "2025-07-01", period_end: "2025-12-31", days: 184, amount: "120.92", accumulated: "120.92", net_book_value: "1079.08", status: "CALCULATED", accounting_entry_id: null, depreciation_account: "281840" }]);
    throw new Error(`Unexpected ${url}`);
  });
  render(<AssetsPage />);
  expect(await screen.findByText("Terrain protégé : aucun plan d’amortissement")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Calculer les périodes" }));
  expect((await screen.findAllByText("120.92 €")).length).toBe(2);
  expect(screen.getByText("184")).toBeInTheDocument();
  await waitFor(() => expect(calls).toContain("/api/assets/years/1/calculate"));
});
