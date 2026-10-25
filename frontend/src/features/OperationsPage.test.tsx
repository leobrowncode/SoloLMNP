import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import OperationsPage from "./OperationsPage";

function response(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), {
    status: 200, headers: { "Content-Type": "application/json" },
  }));
}

function mockApi(options: {
  loans?: unknown[];
  loanPreview?: unknown;
  loanPreviewResponse?: Promise<Response>;
} = {}) {
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    void init;
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
    if (url === "/api/operations/loans") return response(options.loans ?? []);
    if (url === "/api/operations/loans/1/payments/import/preview") {
      return options.loanPreviewResponse ?? response(options.loanPreview ?? {});
    }
    if (url === "/api/operations/loans/1/payments/import") {
      return response({ ...((options.loanPreview ?? {}) as object), imported: 1 });
    }
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
    await userEvent.click(await screen.findByRole("button", { name: /Transactions/ }));
    expect(await screen.findByText(/Assurance · 100.00 €/)).toBeInTheDocument();
    expect(screen.getByText(/Reste à régler : 40.00 €/)).toBeInTheDocument();
    expect(screen.getByText(/La part déductible ne change pas l’écriture/)).toBeInTheDocument();
  });

  it("explains the Google Sheets paste and the paid column", async () => {
    mockApi();
    render(<OperationsPage />);
    await userEvent.click(await screen.findByRole("button", { name: /Transactions/ }));
    await userEvent.click(await screen.findByText("Importer depuis Google Sheets ou un CSV"));
    expect(screen.getByText(/sinon elle reste à régler/)).toBeInTheDocument();
    expect(screen.getByText(/kind date piece_date type counterparty amount description piece_reference source_file/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prévisualiser les justificatifs" })).toBeDisabled();
  });

  it("states that importing a bank file does not post accounting entries", async () => {
    mockApi();
    render(<OperationsPage />);
    await userEvent.click(await screen.findByRole("button", { name: /Banque/ }));
    await userEvent.click(screen.getByText("Importer un relevé CSV"));
    expect(screen.getByText(/L’import seul ne comptabilise rien/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prévisualiser l’import" })).toBeDisabled();
  });

  it("orders setup tabs like the tutorial", async () => {
    mockApi();
    render(<OperationsPage />);
    const tabs = await screen.findAllByRole("button", { pressed: false });
    const names = screen.getAllByRole("button").map((node) => node.textContent).filter((text) =>
      text && /Biens|Banque|Emprunts|Transactions/.test(text),
    );
    expect(names.slice(0, 4).map((text) => text?.replace(/^\d+\s*/, "").trim())).toEqual([
      "Biens", "Banque", "Emprunts", "Transactions",
    ]);
    expect(tabs.length).toBeGreaterThan(0);
  });

  it("previews and imports pasted loan payments for the selected year", async () => {
    const fetcher = mockApi({
      loans: [{
        id: 1, lender: "Banque fictive", property_id: 1, initial_principal: "15000.00",
        remaining_principal: "15000.00", monthly_payment: "62.58",
        monthly_insurance: "4.53", principal_account: "164000",
        interest_rate_basis_points: 150,
      }],
      loanPreview: {
        count: 1, source_count: 2, imported: 0, outside_year: 1, future: 0,
        loan_reference: "085644F", preview_token: "a".repeat(64),
        rows: [{
          loan_reference: "085644F", rank: "1", due_date: "2025-03-05",
          date: "2025-03-05",
          principal: "100.00", interest: "20.00", insurance: "5.00",
          other_costs: "0.00", amount: "125.00", duplicate: false,
          piece_reference: "ECH-164000-2025-03-05",
        }],
      },
    });
    render(<OperationsPage />);
    await userEvent.click(await screen.findByRole("button", { name: /Emprunts/ }));
    await userEvent.click(screen.getByText("Importer les échéances depuis Google Sheets ou un CSV"));
    expect(screen.getByText(/Assurance externe à compléter/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Lignes du tableau d’amortissement"), {
      target: {
        value: "Prêt\tRang\tDate\tCapital (€)\tIntérêts (€)\tAssurance banque (€)\t"
          + "Assurance externe à compléter (€)\tTotal banque (€)\n"
          + "085644F\t1\t05/03/2025\t100,00\t20,00\t5,00\t\t125,00\n",
      },
    });
    await userEvent.click(screen.getByRole("button", { name: "Prévisualiser les échéances" }));
    expect(await screen.findByText(/1 échéance\(s\) retenue\(s\) sur 2/)).toBeInTheDocument();
    expect(screen.getByText("100.00 €")).toBeInTheDocument();
    expect(screen.getByText("20.00 €")).toBeInTheDocument();
    expect(screen.getByText("5.00 €")).toBeInTheDocument();
    const importButton = screen.getByRole("button", { name: "Comptabiliser les échéances" });
    expect(importButton).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: /prêt source 085644F/ }));
    expect(importButton).toBeEnabled();
    await userEvent.click(importButton);
    expect(await screen.findByText(/1 échéance\(s\) comptabilisée\(s\)/)).toBeInTheDocument();
    const importCall = fetcher.mock.calls.find(([url]) =>
      url === "/api/operations/loans/1/payments/import"
    );
    const importedBody = JSON.parse(String(importCall?.[1]?.body)) as Record<string, unknown>;
    expect(importedBody.preview_token).toBe("a".repeat(64));
    expect(importedBody.confirmed_loan_reference).toBe("085644F");
  });

  it("discards a late loan preview after the pasted content changes", async () => {
    let resolvePreview: (value: Response) => void = () => undefined;
    const pendingPreview = new Promise<Response>((resolve) => { resolvePreview = resolve; });
    mockApi({
      loans: [{
        id: 1, lender: "Banque fictive", property_id: 1, initial_principal: "15000.00",
        remaining_principal: "15000.00", monthly_payment: "62.58",
        monthly_insurance: "4.53", principal_account: "164000",
        interest_rate_basis_points: 150,
      }],
      loanPreviewResponse: pendingPreview,
    });
    render(<OperationsPage />);
    await userEvent.click(await screen.findByRole("button", { name: /Emprunts/ }));
    await userEvent.click(screen.getByText("Importer les échéances depuis Google Sheets ou un CSV"));
    const input = screen.getByLabelText("Lignes du tableau d’amortissement");
    fireEvent.change(input, { target: { value: "ancien contenu" } });
    await userEvent.click(screen.getByRole("button", { name: "Prévisualiser les échéances" }));
    fireEvent.change(input, { target: { value: "nouveau contenu" } });
    resolvePreview(new Response(JSON.stringify({
      count: 1, source_count: 1, imported: 0, outside_year: 0, future: 0,
      loan_reference: "085644F", preview_token: "a".repeat(64), rows: [],
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Prévisualiser les échéances" })).toBeEnabled();
    });
    expect(screen.queryByText(/échéance\(s\) retenue\(s\)/)).not.toBeInTheDocument();
  });

  it("prefills loyer type and an automatic piece reference on new revenue", async () => {
    mockApi();
    render(<OperationsPage />);
    await userEvent.click(await screen.findByRole("button", { name: /Transactions/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Nouvelle recette" }));
    expect(screen.getByRole("combobox", { name: /Type d.opération/ })).toHaveValue("LOY");
    expect(screen.getByRole("textbox", { name: /Référence justificative/ })).toHaveValue("LOY-XXXX-XX-SANSNOM");
    expect(screen.getByText(/Générée automatiquement/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Date comptable"), { target: { value: "2026-03-15" } });
    await userEvent.type(screen.getByLabelText("Locataire / client"), "Dupont");
    expect(screen.getByRole("textbox", { name: /Référence justificative/ })).toHaveValue("LOY-2026-03-Dupont");
  });
});
