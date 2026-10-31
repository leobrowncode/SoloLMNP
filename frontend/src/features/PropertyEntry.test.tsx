import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import PropertyEntry from "./PropertyEntry";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});
afterEach(() => vi.restoreAllMocks());

test("previews then posts the property entry with loans and pre-start costs", async () => {
  const bodies: Record<string, unknown>[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url === "/api/operations/loans") {
      return response([{ id: 1, lender: "Banque", property_id: 1, initial_principal: "15000.00", remaining_principal: "0.00", monthly_payment: "58.00", monthly_insurance: "0.00", principal_account: "164000" }]);
    }
    if (url === "/api/operations/banks") return response([{ id: 1, name: "Banque", account_number: "512000" }]);
    if (url === "/api/assets/properties/1/entry") {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      bodies.push(body);
      return response({
        accounting_date: "2026-04-06",
        piece_date: "2026-01-09",
        owner_contribution: "1078.00",
        posted: body.confirm === true,
        entry_number: "2026-000001",
        lines: [{ account_number: "213000", label: "Gros œuvre", debit: "53704.80", credit: "0.00" }],
      });
    }
    throw new Error(`Unexpected ${url}`);
  });
  const done = vi.fn();
  render(<PropertyEntry properties={[{ id: 1, name: "Mérignac 1", acquisition_price: "145000.00", land_value: "29000.00", building_value: "116000.00" }]} years={[{ id: 1, year: 2026 }]} onDone={done} />);

  fireEvent.click(screen.getByRole("button", { name: "Faire entrer le bien en comptabilité" }));
  const outstanding = await screen.findByLabelText(/Capital restant dû au début de l’exercice/);
  fireEvent.change(outstanding, { target: { value: "14 884,00" } });
  fireEvent.change(screen.getByLabelText(/Intérêts d’emprunt payés avant/), { target: { value: "1200" } });
  expect(screen.getByRole("button", { name: "Comptabiliser" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Prévisualiser l’écriture" }));
  expect(await screen.findByText(/apport de l’exploitant/)).toHaveTextContent("apport de l’exploitant 1 078,00 €");
  expect(bodies[0]).toMatchObject({
    confirm: false,
    loans: [{ loan_id: 1, outstanding: "14884.00" }],
    prior_charges: [{ account_number: "661000", amount: "1200.00" }],
  });
  fireEvent.click(screen.getByRole("button", { name: "Comptabiliser" }));
  await vi.waitFor(() => expect(done).toHaveBeenCalledOnce());
  const status = screen.getByRole("status");
  expect(status).toHaveTextContent("Bien entré en comptabilité (écriture 2026-000001).");
  expect(status).toHaveTextContent(/Écriture “Mérignac 1” comptabilisée à \d{2}:\d{2}/);
  expect(status).not.toHaveFocus();
  expect(bodies[1]).toMatchObject({ confirm: true });
});

test("keeps an in-year loan out of the property entry", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === "/api/operations/loans") {
      return response([
        {
          id: 1, lender: "Crédit ancien", property_id: 1, initial_principal: "15000.00",
          remaining_principal: "0.00", monthly_payment: "0.00", monthly_insurance: "0.00",
          principal_account: "164000", start_date: "2024-06-01",
        },
        {
          id: 2, lender: "Crédit de l’année", property_id: 1, initial_principal: "195000.00",
          remaining_principal: "0.00", monthly_payment: "0.00", monthly_insurance: "0.00",
          principal_account: "164001", start_date: "2026-06-01",
        },
      ]);
    }
    if (url === "/api/operations/banks") return response([]);
    if (url === "/api/assets/properties/1/entry") {
      return response({
        accounting_date: "2026-01-01", piece_date: "2026-01-01", owner_contribution: "0.00",
        posted: false, lines: [],
      });
    }
    throw new Error(url);
  });
  render(<PropertyEntry
    properties={[{ id: 1, name: "Bien", acquisition_price: "1.00", land_value: "0.00", building_value: "1.00" }]}
    years={[{ id: 1, year: 2026, start_date: "2026-01-01", status: "OPEN" }]}
    onDone={vi.fn()}
  />);
  fireEvent.click(screen.getByRole("button", { name: "Faire entrer le bien en comptabilité" }));
  expect(await screen.findByLabelText(/Crédit ancien/)).toBeInTheDocument();
  expect(screen.queryByLabelText(/Crédit de l’année/)).not.toBeInTheDocument();
  expect(screen.getByText(/Crédit de l’année commence pendant l’exercice/)).toBeInTheDocument();
});

test("explains a disabled property entry and the missing preview", () => {
  render(<PropertyEntry properties={[]} years={[]} onDone={vi.fn()} />);
  const start = screen.getByRole("button", { name: "Faire entrer le bien en comptabilité" });
  expect(start).toBeDisabled();
  expect(start).toHaveAttribute("aria-describedby", "property-entry-causes");
  const causes = document.getElementById("property-entry-causes");
  expect(causes).toHaveTextContent("Aucun bien n’est enregistré.");
  expect(causes).toHaveTextContent("Aucun exercice n’est créé.");
  expect(causes?.querySelector('a[href="/operations/biens#ajouter-bien"]')).toBeTruthy();
  expect(causes?.querySelector('a[href="/comptabilite/brouillons#ajouter-exercice"]')).toBeTruthy();
});

test("explains that posting waits for a preview", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === "/api/operations/loans") return response([]);
    if (url === "/api/operations/banks") return response([]);
    throw new Error(url);
  });
  render(<PropertyEntry properties={[{ id: 1, name: "Bien", acquisition_price: "1.00", land_value: "0.00", building_value: "1.00" }]} years={[{ id: 4, year: 2026 }]} onDone={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Faire entrer le bien en comptabilité" }));
  const post = await screen.findByRole("button", { name: "Comptabiliser" });
  expect(post).toBeDisabled();
  expect(post).toHaveAttribute("aria-describedby", "property-entry-post-causes");
  expect(document.getElementById("property-entry-post-causes")).toHaveTextContent("Prévisualisez l’écriture");
  expect(screen.getByRole("button", { name: "Prévisualiser l’écriture" })).toBeEnabled();
});
