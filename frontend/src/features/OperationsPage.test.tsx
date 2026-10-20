import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import OperationsPage from "./OperationsPage";

function response(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), {
    status: 200, headers: { "Content-Type": "application/json" },
  }));
}

function mockApi() {
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    if (url === "/api/operations/properties" && init?.method === "POST") {
      return Promise.resolve(new Response(JSON.stringify({
        detail: [{
          type: "value_error",
          loc: ["body"],
          msg: "Value error, Le terrain et le bâtiment doivent totaliser le prix d’acquisition.",
          input: { address: "ne pas afficher cette adresse" },
        }],
      }), { status: 422, headers: { "Content-Type": "application/json" } }));
    }
    if (url === "/api/ledger/setup") return response({
      activity: { activity_name: "Fictif" },
      years: [{ id: 1, year: 2025, start_date: "2025-01-01", end_date: "2025-12-31", status: "OPEN" }],
    });
    if (url === "/api/ledger/accounts") return response([
      { number: "512000", label: "Banque", account_type: "ASSET", active: true },
      { number: "616000", label: "Assurance", account_type: "EXPENSE", active: true },
      { number: "706000", label: "Prestations", account_type: "INCOME", active: true },
    ]);
    if (url === "/api/operations/properties") return response([{
      id: 1, name: "Bien fictif", acquisition_price: "100000.00",
      land_value: "20000.00", building_value: "80000.00",
    }]);
    if (url === "/api/operations/banks") return response([
      { id: 1, name: "Banque fictive", account_number: "512000" },
    ]);
    if (url === "/api/operations/loans") return response([]);
    if (url.startsWith("/api/operations?")) return response([{
      id: 1, kind: "EXPENSE", property_id: 1, fiscal_year_id: 1,
      date: "2025-02-01", amount: "100.00", description: "Assurance",
      counterparty: "Fournisseur", accounting_entry_id: 5,
      remaining_to_settle: "40.00", status: "POSTED",
      deductible_percentage: "80.00", fiscal_treatment: "PARTIAL",
      principal: "0.00", interest: "0.00", insurance: "0.00", other_costs: "0.00",
    }]);
    if (url.startsWith("/api/operations/bank/transactions")) return response([]);
    return response({});
  });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}

describe("OperationsPage", () => {
  it("shows the accounting amount and outstanding settlement separately", async () => {
    mockApi();
    render(<OperationsPage />);
    expect(await screen.findByText(/Assurance · 100.00 €/)).toBeInTheDocument();
    expect(screen.getByText(/Reste à régler : 40.00 €/)).toBeInTheDocument();
    expect(screen.getByText(/Le pourcentage fiscal.+ne réduit jamais le montant/s)).toBeInTheDocument();
  });

  it("states that importing a bank file does not post accounting entries", async () => {
    mockApi();
    render(<OperationsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Banque" }));
    await userEvent.click(screen.getByText("Importer un relevé CSV"));
    expect(screen.getByText(/L’import seul ne comptabilise rien/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prévisualiser l’import" })).toBeDisabled();
  });

  it("shows the property split refusal instead of a generic error", async () => {
    mockApi();
    render(<OperationsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Biens" }));
    await userEvent.click(screen.getByRole("button", { name: "Ajouter un bien" }));
    fireEvent.change(screen.getByLabelText("Nom du bien"), { target: { value: "Studio fictif" } });
    fireEvent.change(screen.getByLabelText("Adresse"), { target: { value: "1 rue du Test" } });
    fireEvent.change(screen.getByLabelText("Date d’acquisition"), { target: { value: "2025-01-15" } });
    fireEvent.change(screen.getByLabelText("Prix d’acquisition (€)"), { target: { value: "100.00" } });
    fireEvent.change(screen.getByLabelText("Valeur du terrain (€)"), { target: { value: "40.00" } });
    fireEvent.change(screen.getByLabelText("Valeur du bâtiment (€)"), { target: { value: "50.00" } });
    await userEvent.click(screen.getByRole("button", { name: "Vérifier avant enregistrement" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer l’enregistrement" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Le terrain et le bâtiment doivent totaliser le prix d’acquisition.",
    );
    expect(screen.queryByText(/Value error/)).not.toBeInTheDocument();
    expect(screen.queryByText(/ne pas afficher/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Opération refusée/)).not.toBeInTheDocument();
  });
});
