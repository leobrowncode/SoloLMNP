import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import AssetsPage from "./AssetsPage";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const period = { id: 2, target_type: "ASSET", target_id: 2, target_label: "Mobilier", base: "1200.00", period_start: "2025-07-01", period_end: "2025-12-31", days: 184, amount: "120.92", accumulated: "120.92", net_book_value: "1079.08", status: "CALCULATED", accounting_entry_id: null, depreciation_account: "281840" };
function deferred() {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>((finish) => { resolve = finish; });
  return { promise, resolve };
}
function mockApi(periods: (url: string) => Promise<Response>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === "/api/ledger/setup") return response({ activity: { id: 1 }, years: [1, 2].map((id) => ({ id, year: 2024 + id, status: "OPEN" })) });
    if (url === "/api/ledger/accounts") return response([]);
    if (url === "/api/operations/properties") return response([{ id: 1, name: "Bien fictif" }]);
    if (url === "/api/assets") return response([{ id: 1, property_id: 1, category: "LAND", label: "Terrain fictif", acquisition_value: "20000.00", depreciable_value: "0.00", non_depreciable_value: "20000.00", residual_value: "0.00", useful_life_months: null, method: "NONE", asset_account: "211000", depreciation_account: null, components: [] }]);
    return periods(url);
  });
}
afterEach(() => vi.restoreAllMocks());

test.each([200, 409])("keeps calculated periods when the initial read finishes late (%s)", async (status) => {
  const initial = deferred();
  const fetch = mockApi(async (url) => {
    if (url.endsWith("/periods")) return initial.promise;
    if (url.endsWith("/calculate")) return response([period]);
    throw new Error(`Unexpected ${url}`);
  });
  render(<AssetsPage />);
  expect(await screen.findByText("Terrain protégé : aucun plan d’amortissement")).toBeInTheDocument();
  // Click as soon as the control is rendered; do not wait for the initial read.
  fireEvent.click(screen.getByRole("button", { name: "Calculer les périodes" }));
  expect(await screen.findAllByText("120.92 €")).toHaveLength(2);
  expect(screen.getByText("184")).toBeInTheDocument();
  await act(async () => { initial.resolve(response(status === 200 ? [] : { detail: { message: "Ancienne erreur" } }, status)); });
  expect(screen.getAllByText("120.92 €")).toHaveLength(2);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith("/api/assets/years/1/calculate", expect.objectContaining({ method: "POST" }));
});

test.each([200, 409])("ignores a calculation from the previous year (%s)", async (status) => {
  const calculation = deferred();
  const nextYear = deferred();
  mockApi(async (url) => {
    if (url.endsWith("/calculate")) return calculation.promise;
    if (url.includes("/years/2/")) return nextYear.promise;
    return response([period]);
  });
  render(<AssetsPage />);
  expect(await screen.findAllByText("120.92 €")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "Calculer les périodes" }));
  fireEvent.change(screen.getByLabelText("Exercice"), { target: { value: "2" } });
  expect(screen.queryByText("Mobilier")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Comptabiliser" })).not.toBeInTheDocument();
  await act(async () => { nextYear.resolve(response([{ ...period, id: 3, target_label: "Mobilier 2026", amount: "240.00", accumulated: "360.92" }])); });
  await act(async () => { calculation.resolve(response(status === 200 ? [period] : { detail: { message: "Ancienne erreur" } }, status)); });
  expect(screen.getByText("Mobilier 2026")).toBeInTheDocument();
  expect(screen.getByText("240.00 €")).toBeInTheDocument();
  expect(screen.queryByText("120.92 €")).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

test("closes the posting form and clears calculation feedback when switching years", async () => {
  mockApi(async (url) => response(url.includes("/years/2/") ? [] : [period]));
  render(<AssetsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Calculer les périodes" }));
  expect(await screen.findByRole("status")).toHaveTextContent("1 période(s) calculée(s)");
  fireEvent.click(screen.getByRole("button", { name: "Comptabiliser" }));
  expect(screen.getByLabelText("Référence de la pièce d’inventaire")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Exercice"), { target: { value: "2" } });
  expect(screen.queryByLabelText("Référence de la pièce d’inventaire")).not.toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

test("shows an error from the current calculation", async () => {
  mockApi(async (url) => url.endsWith("/calculate") ? response({ detail: { message: "Calcul refusé" } }, 409) : response([]));
  render(<AssetsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Calculer les périodes" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Calcul refusé");
});

test("previews a dwelling plan, cancels it, then confirms without duplicating", async () => {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const plan = {
    property_id: 1,
    depreciable_base: "80000.00",
    acquisition_costs_included: "0.00",
    labels: ["Terrain — Bien fictif", "Construction — Bien fictif", "Gros œuvre"],
    created: false,
    items: [
      { kind: "LAND", label: "Terrain — Bien fictif", amount: "20000.00", asset_account: "211000", depreciation_account: null, useful_life_months: null },
      { kind: "BUILDING", label: "Construction — Bien fictif", amount: "80000.00", asset_account: "213000", depreciation_account: "281300", useful_life_months: 480 },
      { kind: "COMPONENT", label: "Gros œuvre", amount: "32000.00", asset_account: "213000", depreciation_account: "281300", useful_life_months: 480 },
    ],
  };
  const stored = [{
    id: 1, property_id: 1, category: "LAND", label: "Terrain — Bien fictif",
    acquisition_value: "20000.00", depreciable_value: "0.00", non_depreciable_value: "20000.00",
    residual_value: "0.00", useful_life_months: null, method: "NONE", asset_account: "211000",
    depreciation_account: null, components: [],
  }];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) as unknown : undefined;
    calls.push({ method, url, body });
    if (url === "/api/ledger/setup") return response({ activity: { id: 1 }, years: [{ id: 1, year: 2025, status: "OPEN" }] });
    if (url === "/api/ledger/accounts") return response([]);
    if (url === "/api/operations/properties") return response([{ id: 1, name: "Bien fictif" }]);
    if (url === "/api/assets/years/1/periods") return response([]);
    if (url === "/api/assets/properties/1/plan" && method === "GET") return response(plan);
    if (url === "/api/assets/properties/1/plan" && method === "POST") {
      const posts = calls.filter((call) => call.url.endsWith("/plan") && call.method === "POST").length;
      return response({ ...plan, created: posts === 1 }, posts === 1 ? 201 : 200);
    }
    if (url === "/api/assets") {
      const posts = calls.filter((call) => call.url.endsWith("/plan") && call.method === "POST").length;
      return response(posts > 0 ? stored : []);
    }
    throw new Error(`Unexpected ${method} ${url}`);
  });
  render(<AssetsPage />);
  const preview = await screen.findByRole("button", { name: "Prévisualiser l’amortissement du logement" });
  expect(screen.queryByRole("button", { name: "Créer les immobilisations affichées" })).not.toBeInTheDocument();
  fireEvent.click(preview);
  expect(await screen.findByText("Non amortissable")).toBeInTheDocument();
  expect(screen.getByText("Terrain — Bien fictif")).toBeInTheDocument();
  expect(screen.getByText("Construction — Bien fictif")).toBeInTheDocument();
  expect(screen.getByText("Gros œuvre")).toBeInTheDocument();
  expect(screen.getByText("20000.00 €")).toBeInTheDocument();
  expect(screen.getByText("211000")).toBeInTheDocument();
  expect(screen.getAllByText("480 mois")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
  expect(screen.queryByText("Gros œuvre")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Créer les immobilisations affichées" })).not.toBeInTheDocument();
  expect(calls.some((call) => call.method === "POST")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Prévisualiser l’amortissement du logement" }));
  fireEvent.click(await screen.findByRole("button", { name: "Créer les immobilisations affichées" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Immobilisations créées : Terrain — Bien fictif, Construction — Bien fictif, Gros œuvre.");
  expect(await screen.findByText("Terrain protégé : aucun plan d’amortissement")).toBeInTheDocument();
  expect(screen.getAllByText("Terrain — Bien fictif")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Prévisualiser l’amortissement du logement" }));
  fireEvent.click(await screen.findByRole("button", { name: "Créer les immobilisations affichées" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Ces immobilisations existent déjà. Aucun doublon n’a été créé.");
  expect(screen.getAllByText("Terrain — Bien fictif")).toHaveLength(1);
  const posts = calls.filter((call) => call.url === "/api/assets/properties/1/plan" && call.method === "POST");
  expect(posts).toHaveLength(2);
  expect(posts.every((call) => JSON.stringify(call.body) === JSON.stringify({ confirm: true }))).toBe(true);
  expect(calls.filter((call) => call.url.endsWith("/plan") && call.method === "GET").length).toBeGreaterThanOrEqual(2);
});
