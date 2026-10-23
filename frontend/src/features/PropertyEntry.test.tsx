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
  expect(await screen.findByText(/apport de l’exploitant 1078.00 €/)).toBeInTheDocument();
  expect(bodies[0]).toMatchObject({
    confirm: false,
    loans: [{ loan_id: 1, outstanding: "14884.00" }],
    prior_charges: [{ account_number: "661000", amount: "1200.00" }],
  });
  fireEvent.click(screen.getByRole("button", { name: "Comptabiliser" }));
  await vi.waitFor(() => expect(done).toHaveBeenCalledWith("Bien entré en comptabilité (écriture 2026-000001)."));
  expect(bodies[1]).toMatchObject({ confirm: true });
});
