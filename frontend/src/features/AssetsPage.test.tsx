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

test("an initial failure is an error, not a missing activity", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Hors ligne"));
  render(<AssetsPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Hors ligne");
  expect(screen.queryByText(/Initialisez d’abord/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Chargement des immobilisations/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
});

test("shows an error from the current calculation", async () => {
  mockApi(async (url) => url.endsWith("/calculate") ? response({ detail: { message: "Calcul refusé" } }, 409) : response([]));
  render(<AssetsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Calculer les périodes" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Calcul refusé");
});

const dwellingPlan = {
  property_id: 1,
  depreciable_base: "80000.00",
  acquisition_costs_included: "0.00",
  labels: ["Terrain — Bien fictif", "Construction — Bien fictif", "Gros œuvre"],
  preview_token: "ab".repeat(32),
  created: false,
  items: [
    { kind: "LAND", label: "Terrain — Bien fictif", amount: "20000.00", asset_account: "211000", depreciation_account: null, useful_life_months: null, service_start_date: "2025-01-01" },
    { kind: "BUILDING", label: "Construction — Bien fictif", amount: "80000.00", asset_account: "213000", depreciation_account: "281300", useful_life_months: 480, service_start_date: "2025-01-01" },
    { kind: "COMPONENT", label: "Gros œuvre", amount: "32000.00", asset_account: "213000", depreciation_account: "281300", useful_life_months: 480, service_start_date: "2025-01-01" },
  ],
};

test("previews a dwelling plan, cancels it, then confirms without duplicating", async () => {
  const calls: { method: string; url: string; body?: unknown }[] = [];
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
    if (url === "/api/assets/properties/1/plan" && method === "GET") return response(dwellingPlan);
    if (url === "/api/assets/properties/1/plan" && method === "POST") {
      const posts = calls.filter((call) => call.url.endsWith("/plan") && call.method === "POST").length;
      return response({ ...dwellingPlan, created: posts === 1 }, posts === 1 ? 201 : 200);
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
  expect(screen.getAllByText("281300")).toHaveLength(2);
  expect(screen.getAllByText("213000")).toHaveLength(2);
  expect(screen.getAllByText("480 mois")).toHaveLength(2);
  expect(screen.getAllByText("2025-01-01").length).toBeGreaterThanOrEqual(3);
  fireEvent.click(screen.getByRole("button", { name: "Annuler l’aperçu" }));
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
  expect(posts.every((call) => JSON.stringify(call.body) === JSON.stringify({ confirm: true, preview_token: dwellingPlan.preview_token }))).toBe(true);
  expect(calls.filter((call) => call.url.endsWith("/plan") && call.method === "GET")).toHaveLength(3);
  expect(calls.filter((call) => call.method === "POST").every((call) => call.url.endsWith("/plan"))).toBe(true);
});

test("drops a dwelling preview started for another property", async () => {
  const first = deferred();
  const calls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    calls.push(`${method} ${url}`);
    if (url === "/api/ledger/setup") return response({ activity: { id: 1 }, years: [{ id: 1, year: 2025, status: "OPEN" }] });
    if (url === "/api/ledger/accounts") return response([]);
    if (url === "/api/operations/properties") return response([{ id: 1, name: "Bien fictif" }, { id: 2, name: "Autre bien" }]);
    if (url === "/api/assets" || url.endsWith("/periods")) return response([]);
    if (url === "/api/assets/properties/1/plan") return first.promise;
    throw new Error(`Unexpected ${method} ${url}`);
  });
  render(<AssetsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Prévisualiser l’amortissement du logement" }));
  fireEvent.change(screen.getByLabelText("Logement"), { target: { value: "2" } });
  await act(async () => { first.resolve(response(dwellingPlan)); });
  expect(screen.queryByText("Gros œuvre")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Créer les immobilisations affichées" })).not.toBeInTheDocument();
  expect(calls.some((call) => call.startsWith("POST"))).toBe(false);
});

const chart = [
  ["211000", "Terrains"], ["211100", "Autre terrain"], ["213000", "Constructions"],
  ["213100", "Construction inactive"], ["213500", "Installations"], ["218300", "Matériel"],
  ["218400", "Mobilier"], ["218500", "Autre corporel"], ["281300", "Amort. constructions"],
  ["281350", "Amort. installations"], ["281830", "Amort. matériel"], ["281840", "Amort. mobilier"],
  ["281850", "Amort. autre"], ["512000", "Banques"],
].map(([number, label], index) => ({ number, label, account_type: "ASSET", active: index !== 3 }));

function optionValues(label: string): string[] {
  return [...(screen.getByLabelText(label) as HTMLSelectElement).options].map((option) => option.value);
}

test("proposes only the accounts of the selected category", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === "/api/ledger/setup") return response({ activity: { id: 1 }, years: [{ id: 1, year: 2025, status: "OPEN" }] });
    if (url === "/api/ledger/accounts") return response(chart);
    if (url === "/api/operations/properties") return response([{ id: 1, name: "Bien fictif" }]);
    if (url === "/api/assets") return response([{
      id: 2, property_id: 1, category: "BUILDING", label: "Construction fictive",
      acquisition_value: "80000.00", depreciable_value: "80000.00", non_depreciable_value: "0.00",
      residual_value: "0.00", useful_life_months: 360, method: "LINEAR",
      asset_account: "213000", depreciation_account: "281300", components: [],
    }]);
    if (url.endsWith("/periods")) return response([]);
    throw new Error(`Unexpected ${url}`);
  });
  render(<AssetsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Nouvelle immobilisation" }));
  expect(screen.getByLabelText("Catégorie")).toHaveValue("BUILDING");
  expect(screen.getByLabelText("Compte d’immobilisation")).toHaveValue("213000");
  expect(screen.getByLabelText("Compte d’amortissement")).toHaveValue("281300");
  expect(optionValues("Compte d’immobilisation")).toEqual(["213000"]);
  expect(optionValues("Compte d’amortissement")).toEqual(["281300"]);
  for (const category of ["FURNITURE", "EQUIPMENT", "IMPROVEMENT", "OTHER"] as const) {
    fireEvent.change(screen.getByLabelText("Catégorie"), { target: { value: category } });
  }
  expect(screen.getByLabelText("Compte d’immobilisation")).toHaveValue("218500");
  expect(screen.getByLabelText("Compte d’amortissement")).toHaveValue("281850");
  expect(optionValues("Compte d’immobilisation")).toEqual(["218500"]);
  expect(optionValues("Compte d’amortissement")).not.toContain("281300");
  fireEvent.change(screen.getByLabelText("Catégorie"), { target: { value: "FURNITURE" } });
  expect(screen.getByLabelText("Compte d’immobilisation")).toHaveValue("218400");
  expect(optionValues("Compte d’immobilisation")).toEqual(["218400"]);
  expect(optionValues("Compte d’amortissement")).toEqual(["281840"]);
  fireEvent.change(screen.getByLabelText("Catégorie"), { target: { value: "EQUIPMENT" } });
  expect(optionValues("Compte d’immobilisation")).toEqual(["218300"]);
  expect(optionValues("Compte d’amortissement")).toEqual(["281830"]);
  fireEvent.change(screen.getByLabelText("Catégorie"), { target: { value: "IMPROVEMENT" } });
  expect(optionValues("Compte d’immobilisation")).toEqual(["213500"]);
  expect(optionValues("Compte d’amortissement")).toEqual(["281350"]);
  fireEvent.change(screen.getByLabelText("Catégorie"), { target: { value: "BUILDING" } });
  expect(optionValues("Compte d’immobilisation")).toEqual(["213000"]);
  expect(optionValues("Compte d’immobilisation")).not.toEqual(expect.arrayContaining(["211000", "281300", "512000"]));
  fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
  fireEvent.click(screen.getByRole("button", { name: "Inscrire un terrain" }));
  expect(screen.getByLabelText("Compte d’immobilisation")).toHaveValue("211000");
  expect(optionValues("Compte d’immobilisation")).toEqual(["211000", "211100"]);
  expect(screen.queryByLabelText("Compte d’amortissement")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
  fireEvent.click(screen.getByRole("button", { name: "Ajouter un composant" }));
  expect(optionValues("Compte d’immobilisation")).toEqual(["213000", "213500"]);
  expect(optionValues("Compte d’amortissement")).toEqual(["281300"]);
  fireEvent.change(screen.getByLabelText("Compte d’immobilisation"), { target: { value: "213500" } });
  expect(screen.getByLabelText("Compte d’amortissement")).toHaveValue("281350");
  expect(optionValues("Compte d’amortissement")).toEqual(["281350"]);
});

test("shows an inconsistent stored pair without offering to rewrite it", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === "/api/ledger/setup") return response({ activity: { id: 1 }, years: [{ id: 1, year: 2025, status: "OPEN" }] });
    if (url === "/api/ledger/accounts") return response([]);
    if (url === "/api/operations/properties") return response([{ id: 1, name: "Bien fictif" }]);
    if (url.endsWith("/periods")) return response([]);
    if (url === "/api/assets") return response([{
      id: 3, property_id: 1, category: "BUILDING", label: "Construction incohérente",
      acquisition_value: "80000.00", depreciable_value: "80000.00", non_depreciable_value: "0.00",
      residual_value: "0.00", useful_life_months: 360, method: "LINEAR",
      asset_account: "211000", depreciation_account: "281300",
      account_warning: "Le compte 211000 correspond à Terrain. Le registre et les écritures ne sont pas réécrits.",
      components: [{
        id: 9, asset_id: 3, category: "STRUCTURE", label: "Mauvais composant", value: "1000.00",
        useful_life_months: 120, service_start_date: "2025-01-01",
        account_warning: "Le compte 218400 n’est pas autorisé. Le registre et les écritures ne sont pas réécrits.",
      }],
    }]);
    throw new Error(`Unexpected ${url}`);
  });
  render(<AssetsPage />);
  expect(await screen.findByText(/Le compte 211000 correspond à Terrain/)).toBeInTheDocument();
  expect(screen.getByText(/Le compte 218400 n’est pas autorisé/)).toBeInTheDocument();
  expect(screen.getByText(/211000 \/ 281300/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Corriger" })).not.toBeInTheDocument();
});

const postedLock = {
  locks: [{
    code: "DEPRECIATION_POSTED",
    fields: ["value", "life", "dates", "account"],
    message: "Une dotation est déjà comptabilisée.",
  }],
  calculated_periods: 0,
};

test("hides frozen asset fields and patches the duration while it is still free", async () => {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) as unknown : undefined;
    calls.push({ url, method, body });
    if (url === "/api/ledger/setup") return response({ activity: { id: 1 }, years: [{ id: 1, year: 2025, status: "OPEN" }] });
    if (url === "/api/ledger/accounts") return response([
      { number: "218400", label: "Mobilier", account_type: "ASSET", active: true },
      { number: "281840", label: "Amort. mobilier", account_type: "ASSET", active: true },
    ]);
    if (url === "/api/operations/properties") return response([{ id: 1, name: "Bien fictif" }]);
    if (url.endsWith("/periods")) return response([]);
    if (url === "/api/assets" && method === "GET") return response([
      {
        id: 4, property_id: 1, category: "FURNITURE", label: "Mobilier figé",
        acquisition_date: "2025-07-01", service_start_date: "2025-07-01",
        acquisition_value: "1200.00", depreciable_value: "1200.00", non_depreciable_value: "0.00",
        residual_value: "0.00", useful_life_months: 60, method: "LINEAR",
        asset_account: "218400", depreciation_account: "281840",
        basis_reason: "Facture fictive", duration_reason: "Cinq ans d’usage",
        correction: postedLock, components: [],
      },
      {
        id: 5, property_id: 1, category: "FURNITURE", label: "Mobilier libre",
        acquisition_date: "2025-07-01", service_start_date: "2025-07-01",
        acquisition_value: "1200.00", depreciable_value: "1200.00", non_depreciable_value: "0.00",
        residual_value: "0.00", useful_life_months: 60, method: "LINEAR",
        asset_account: "218400", depreciation_account: "281840",
        basis_reason: "Facture fictive", duration_reason: "Cinq ans d’usage",
        correction: { locks: [], calculated_periods: 1 }, components: [],
      },
    ]);
    if (url === "/api/assets/5" && method === "PATCH") {
      return response({
        invalidation: {
          dropped_period_ids: [8], fiscal_computations: 0,
          ready_years_reset: [], snapshots_superseded: 0,
        },
      });
    }
    throw new Error(`Unexpected ${method} ${url}`);
  });
  render(<AssetsPage />);
  expect(await screen.findByText("Une dotation est déjà comptabilisée.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Préciser la justification de Mobilier figé" }));
  expect(screen.queryByLabelText("Valeur d’acquisition (€)")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Durée d’utilisation en mois")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Compte d’immobilisation")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Justification de la valeur")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
  fireEvent.click(screen.getByRole("button", { name: "Modifier Mobilier libre" }));
  fireEvent.change(screen.getByLabelText("Durée d’utilisation en mois"), { target: { value: "84" } });
  fireEvent.change(screen.getByLabelText("Motif de la correction (au moins 5 caractères)"), {
    target: { value: "Durée d’usage revue" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Vérifier avant enregistrement" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirmer l’enregistrement" }));
  expect(await screen.findByRole("status")).toHaveTextContent("1 période(s) calculée(s)");
  const sent = calls.find((call) => call.url === "/api/assets/5" && call.method === "PATCH");
  expect(sent?.body).toMatchObject({ useful_life_months: 84, reason: "Durée d’usage revue" });
});

test("names the missing property on every immobilisation action", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === "/api/ledger/setup") return response({
      activity: { id: 1 },
      years: [{ id: 1, year: 2025, status: "CLOSED" }],
    });
    if (url === "/api/ledger/accounts") return response([]);
    if (url === "/api/operations/properties") return response([]);
    if (url === "/api/assets") return response([]);
    return response([]);
  });
  render(<AssetsPage />);
  const create = await screen.findByRole("button", { name: "Nouvelle immobilisation" });
  const land = screen.getByRole("button", { name: "Inscrire un terrain" });
  const plan = screen.getByRole("button", { name: "Prévisualiser l’amortissement du logement" });
  const entry = screen.getByRole("button", { name: "Faire entrer le bien en comptabilité" });
  const calculate = screen.getByRole("button", { name: "Calculer les périodes" });
  for (const button of [create, land, plan, entry]) expect(button).toBeDisabled();
  expect(create).toHaveAttribute("aria-describedby", "asset-create-causes");
  expect(land).toHaveAttribute("aria-describedby", "asset-create-causes");
  expect(document.getElementById("asset-create-causes")).toHaveTextContent("Aucun bien n’est enregistré.");
  expect(document.getElementById("asset-plan-causes")).toHaveTextContent("Aucun bien n’est enregistré.");
  const entryCauses = document.getElementById("property-entry-causes");
  expect(entryCauses).toHaveTextContent("Aucun bien n’est enregistré.");
  expect(entryCauses).toHaveTextContent("clôturé");
  expect(entryCauses?.querySelector('a[href="/operations/biens#ajouter-bien"]')).toBeTruthy();
  expect(entryCauses?.querySelector('a[href="/fiscalite#reopen-title"]')).toBeTruthy();
  expect(calculate).toBeDisabled();
  expect(document.getElementById("asset-period-causes")).toHaveTextContent("clôturé");
  const post = screen.getByRole("button", { name: "Comptabiliser toutes les dotations" });
  expect(post).toBeDisabled();
  expect(post).toHaveAttribute("aria-describedby", expect.stringContaining("asset-period-causes"));
});
