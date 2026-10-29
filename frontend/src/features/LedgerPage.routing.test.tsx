import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ledgerPath, type LedgerTab } from "../routing/paths";
import LedgerPage from "./LedgerPage";

const accounts = [
  { number: "512000", label: "Banque", active: true, account_type: "ASSET" },
  { number: "706000", label: "Prestations", active: true, account_type: "INCOME" },
];
function mockApi() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = url.replace("/api/ledger", "");
    let data: unknown = {};
    if (path === "/setup") data = { activity: { activity_name: "Fictif" }, years: [{ id: 1, year: 2025, start_date: "2025-01-01", end_date: "2025-12-31", status: "OPEN" }] };
    if (path === "/accounts") data = accounts;
    if (path === "/journals") data = [{ code: "OD", label: "Opérations", active: true }];
    if (path.startsWith("/entries?")) data = { entries: [], count: 0 };
    return new Response(JSON.stringify(data), { status: 200 });
  }));
}

function renderLedger(tab: LedgerTab = "Balance") {
  return render(
    <MemoryRouter initialEntries={[ledgerPath(tab)]}>
      <Routes>
        <Route path="/comptabilite/:tab" element={<LedgerPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ledger routing", () => {
  it("selects the balance tab from the URL", async () => {
    mockApi();
    renderLedger("Balance");
    expect(await screen.findByRole("button", { name: "Balance", pressed: true })).toBeInTheDocument();
  });
});
