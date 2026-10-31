import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { operationsPath } from "../routing/paths";
import { renderWithRouter } from "../routing/testPage";
import OperationsPage from "./OperationsPage";

function renderOperations(tab: "Biens" | "Banque" | "Emprunts" | "Transactions" = "Biens") {
  return renderWithRouter(<OperationsPage />, operationsPath(tab), "/operations/:tab");
}

function response(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), {
    status: 200, headers: { "Content-Type": "application/json" },
  }));
}

function mockApi(options: {
  loans?: unknown[];
  loanPreview?: unknown;
  loanPreviewResponse?: Promise<Response>;
  properties?: unknown[];
  years?: unknown[];
  banks?: unknown[] | null;
  operations?: unknown[];
  entries?: Record<string, unknown>;
} = {}) {
  const properties = options.properties ?? [{
    id: 1, name: "Bien fictif", acquisition_price: "100000.00",
    land_value: "20000.00", building_value: "80000.00",
  }];
  const years = options.years ?? [{ id: 1, year: 2025, start_date: "2025-01-01", end_date: "2025-12-31", status: "OPEN" }];
  const banks = options.banks === null ? [] : (options.banks ?? [
    { id: 1, name: "Banque fictive", account_number: "512000" },
  ]);
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    void init;
    if (url === "/api/ledger/setup") return response({
      activity: { activity_name: "Fictif" },
      years,
    });
    if (url === "/api/ledger/accounts") return response([
      { number: "512000", label: "Banque", account_type: "ASSET", active: true },
      { number: "616000", label: "Assurance", account_type: "EXPENSE", active: true },
      { number: "706000", label: "Prestations", account_type: "INCOME", active: true },
    ]);
    if (url === "/api/operations/properties") return response(properties);
    if (url === "/api/operations/banks") return response(banks);
    if (url === "/api/operations/loans") return response(options.loans ?? []);
    if (url === "/api/operations/imports/loan_payments/preview") {
      return options.loanPreviewResponse ?? response(options.loanPreview ?? {});
    }
    if (url === "/api/operations/imports/loan_payments/commit") {
      return response({ ...((options.loanPreview ?? {}) as object), imported: 1 });
    }
    if (url.startsWith("/api/operations?")) return response(options.operations ?? [{
      id: 1, kind: "EXPENSE", property_id: 1, fiscal_year_id: 1,
      date: "2025-02-01", amount: "100.00", description: "Assurance",
      counterparty: "Fournisseur", accounting_entry_id: 5,
      remaining_to_settle: "40.00", status: "POSTED",
      deductible_percentage: "80.00", fiscal_treatment: "PARTIAL",
      principal: "0.00", interest: "0.00", insurance: "0.00", other_costs: "0.00",
    }]);
    if (url.startsWith("/api/operations/bank/transactions")) return response([]);
    if (url.startsWith("/api/ledger/entries/")) {
      const id = url.slice(url.lastIndexOf("/") + 1);
      return response(options.entries?.[id] ?? {});
    }
    return response({});
  });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}

describe("OperationsPage", () => {
  it("shows the accounting amount and outstanding settlement separately", async () => {
    mockApi();
    renderOperations();
    await userEvent.click(await screen.findByRole("button", { name: /Transactions/ }));
    expect(await screen.findByText(/Assurance · 100,00 €/)).toBeInTheDocument();
    expect(screen.getByText(/Reste à régler : 40,00 €/)).toBeInTheDocument();
    expect(screen.getByText(/La part déductible ne change pas l’écriture/)).toBeInTheDocument();
  });

  it("explains the Google Sheets paste and the paid column", async () => {
    mockApi();
    renderOperations();
    await userEvent.click(await screen.findByRole("button", { name: /Transactions/ }));
    await userEvent.click(await screen.findByText("Importer depuis Google Sheets ou un CSV"));
    expect(screen.getByText(/sinon elle reste à régler/)).toBeInTheDocument();
    expect(screen.getByText(/Nature, Date, Date de la pièce/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Télécharger le modèle CSV" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prévisualiser les justificatifs" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Prévisualiser les justificatifs" })).toHaveAttribute("aria-describedby", "operation-preview-causes");
    expect(document.getElementById("operation-preview-causes")).toHaveTextContent("Collez ou chargez un fichier");
  });

  it("states that importing a bank file does not post accounting entries", async () => {
    mockApi();
    renderOperations();
    await userEvent.click(await screen.findByRole("button", { name: /Banque/ }));
    await userEvent.click(screen.getByText("Importer un relevé CSV"));
    expect(screen.getByText(/L’import seul ne comptabilise rien/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prévisualiser l’import" })).toBeDisabled();
    expect(document.getElementById("bank-preview-causes")).toHaveTextContent("Collez ou chargez un fichier");
  });

  it("orders setup tabs like the tutorial", async () => {
    mockApi();
    renderOperations();
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
        interest_rate_basis_points: 1500,
      }],
      loanPreview: {
        ready: true,
        headers: ["Prêt", "Date", "Capital", "Total banque"],
        fields: [
          { key: "loan_reference", label: "Prêt", required: true, help: "emprunt" },
          { key: "due_date", label: "Date", required: true, help: "emprunt" },
          { key: "principal", label: "Capital", required: true, help: "compte-164" },
          { key: "amount", label: "Total banque", required: true, help: "emprunt" },
        ],
        mapping: {},
        issues: [],
        loan_reference: "085644F",
        rejects_csv: "",
        imported: 0,
        summary: { valid: 1, duplicate: 0, warning: 1, error: 0, count: 2, importable: 1 },
        rows: [{
          line: 2, status: "valid", importable: true, duplicate: false, suggested_account: null,
          display: { loan_reference: "085644F", due_date: "05/03/2025", principal: "100,00", amount: "125,00" },
          issues: [], warnings: [],
        }, {
          line: 3, status: "warning", importable: false, duplicate: false, suggested_account: null,
          display: { loan_reference: "085644F", due_date: "05/01/2024", principal: "80,00", amount: "90,00" },
          issues: [],
          warnings: [{ code: "DATE_OUTSIDE_YEAR", message: "Échéance hors exercice.", line: 3 }],
        }],
      },
    });
    renderOperations();
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
    expect(await screen.findByText(/1 valide\(s\)/)).toBeInTheDocument();
    expect(screen.getByText(/1 avertissement\(s\)/)).toBeInTheDocument();
    expect(screen.getByText("100,00")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Valide" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Avertissement" })).toBeInTheDocument();
    const importButton = screen.getByRole("button", { name: "Comptabiliser les échéances" });
    expect(importButton).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: /prêt source 085644F/ }));
    expect(importButton).toBeEnabled();
    await userEvent.click(importButton);
    expect(await screen.findByText(/1 échéance comptabilisée/)).toBeInTheDocument();
    const importCall = fetcher.mock.calls.find(([url]) =>
      url === "/api/operations/imports/loan_payments/commit"
    );
    const importedBody = JSON.parse(String(importCall?.[1]?.body)) as Record<string, unknown>;
    expect(importedBody.confirmed_loan_reference).toBe("085644F");
    expect(importedBody.loan_id).toBe(1);
  });

  it("discards a late loan preview after the pasted content changes", async () => {
    let resolvePreview: (value: Response) => void = () => undefined;
    const pendingPreview = new Promise<Response>((resolve) => { resolvePreview = resolve; });
    mockApi({
      loans: [{
        id: 1, lender: "Banque fictive", property_id: 1, initial_principal: "15000.00",
        remaining_principal: "15000.00", monthly_payment: "62.58",
        monthly_insurance: "4.53", principal_account: "164000",
        interest_rate_basis_points: 1500,
      }],
      loanPreviewResponse: pendingPreview,
    });
    renderOperations();
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
    expect(screen.queryByText(/valide\(s\)/)).not.toBeInTheDocument();
  });

  it("prefills loyer type and an automatic piece reference on new revenue", async () => {
    mockApi();
    renderOperations();
    await userEvent.click(await screen.findByRole("button", { name: /Transactions/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Nouvelle recette" }));
    expect(screen.getByRole("combobox", { name: /Type d.opération/ })).toHaveValue("LOY");
    expect(screen.getByRole("textbox", { name: /Référence justificative/ })).toHaveValue("LOY-XXXX-XX-SANSNOM");
    expect(screen.getByText(/Générée automatiquement/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Date comptable"), { target: { value: "2026-03-15" } });
    await userEvent.type(screen.getByLabelText("Locataire / client"), "Dupont");
    expect(screen.getByRole("textbox", { name: /Référence justificative/ })).toHaveValue("LOY-2026-03-Dupont");
  });

  it("explains a locked property, loan and bank without offering the frozen fields", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      const url = String(input);
      if (url === "/api/ledger/setup") return response({
        activity: { activity_name: "Fictif" },
        years: [{ id: 1, year: 2025, start_date: "2025-01-01", end_date: "2025-12-31", status: "OPEN" }],
      });
      if (url === "/api/ledger/accounts") return response([
        { number: "512000", label: "Banque", account_type: "ASSET", active: true },
      ]);
      if (url === "/api/operations/properties") return response([{
        id: 1, name: "Bien fictif", address: "Adresse fictive", acquisition_date: "2025-01-01",
        acquisition_price: "100000.00", acquisition_costs: "0.00", land_value: "20000.00",
        building_value: "80000.00", notes: "",
        correction: {
          locks: [{
            code: "PROPERTY_HAS_ASSETS", fields: ["financial"],
            message: "Des immobilisations existent déjà.",
          }],
          calculated_periods: 0,
        },
      }]);
      if (url === "/api/operations/properties/1/tenants") return response([]);
      if (url === "/api/operations/banks") return response([{
        id: 1, name: "Compte courant", account_number: "512000",
        correction: {
          locks: [{
            code: "BANK_HAS_MOVEMENTS", fields: ["account_number"],
            message: "Des mouvements existent déjà sur ce compte.",
          }],
          calculated_periods: 0,
        },
      }]);
      if (url === "/api/operations/loans") return response([{
        id: 1, lender: "Crédit fictif", property_id: 1, initial_principal: "15000.00",
        remaining_principal: "15000.00", monthly_payment: "62.58", monthly_insurance: "4.53",
        principal_account: "164000", interest_rate: "1.50", interest_rate_basis_points: 1500,
        start_date: "2025-01-01", duration_months: 240,
        correction: {
          locks: [{
            code: "LOAN_ACCOUNT_FIXED", fields: ["principal_account"],
            message: "Le compte 164 identifie l’emprunt et n’est pas modifiable.",
          }],
          calculated_periods: 0,
        },
      }]);
      if (url.startsWith("/api/operations?")) return response([]);
      if (url.startsWith("/api/operations/bank/transactions")) return response([]);
      return response({});
    }));
    renderOperations();
    expect(await screen.findByText("Des immobilisations existent déjà.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Modifier Bien fictif" }));
    expect(screen.getByLabelText("Nom du bien")).toHaveValue("Bien fictif");
    expect(screen.queryByLabelText("Prix d’acquisition (€)")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Annuler" }));
    await userEvent.click(screen.getByRole("button", { name: /Banque/ }));
    expect(screen.getByText("Des mouvements existent déjà sur ce compte.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Modifier Compte courant" }));
    expect(screen.getByLabelText("Nom du compte bancaire")).toHaveValue("Compte courant");
    expect(screen.queryByLabelText("Compte comptable dédié")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Annuler" }));
    await userEvent.click(screen.getByRole("button", { name: /Emprunts/ }));
    expect(screen.getByText("Le compte 164 identifie l’emprunt et n’est pas modifiable.")).toBeInTheDocument();
  });

  it("does not treat a failed load as an empty activity", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Hors ligne")));
    renderOperations();
    expect(await screen.findByRole("alert")).toHaveTextContent("Hors ligne");
    expect(screen.queryByText(/Chargement…/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Initialisez votre activité/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });

  it("lists every missing prerequisite of a new revenue or expense", async () => {
    mockApi({ properties: [], years: [
      { id: 1, year: 2024, status: "CLOSED" },
      { id: 2, year: 2025, status: "READY_TO_CLOSE" },
    ] });
    renderOperations("Transactions");
    const revenue = await screen.findByRole("button", { name: "Nouvelle recette" });
    const expense = screen.getByRole("button", { name: "Nouvelle dépense" });
    expect(revenue).toBeDisabled();
    expect(expense).toBeDisabled();
    expect(revenue).toHaveAttribute("aria-describedby", "operation-entry-causes");
    expect(expense).toHaveAttribute("aria-describedby", "operation-entry-causes");
    const causes = document.getElementById("operation-entry-causes");
    expect(causes).toHaveTextContent("Aucun bien n’est enregistré.");
    expect(causes).toHaveTextContent("au moins un exercice est clôturé");
    expect(causes).toHaveTextContent("au moins un exercice est prêt à clôturer");
    expect(causes?.querySelector('a[href="/operations/biens#ajouter-bien"]')).toHaveTextContent("Ajouter un bien");
    expect(causes?.querySelector('a[href="/fiscalite#reopen-title"]')).toHaveTextContent("Réouvrir l’exercice");
    expect(causes?.querySelector('a[href="/fiscalite#close-title"]')).toHaveTextContent("Voir le pré-contrôle");
  });

  it("names only the missing property when an exercise is open", async () => {
    mockApi({ properties: [] });
    renderOperations("Transactions");
    const revenue = await screen.findByRole("button", { name: "Nouvelle recette" });
    expect(revenue).toBeDisabled();
    const causes = document.getElementById("operation-entry-causes");
    expect(causes).toHaveTextContent("Aucun bien n’est enregistré.");
    expect(causes).not.toHaveTextContent("exercice");
  });

  it("names only the closed exercise when a property exists", async () => {
    mockApi({ years: [{ id: 1, year: 2025, status: "CLOSED" }] });
    renderOperations("Transactions");
    const expense = await screen.findByRole("button", { name: "Nouvelle dépense" });
    expect(expense).toBeDisabled();
    const causes = document.getElementById("operation-entry-causes");
    expect(causes).toHaveTextContent("clôturé");
    expect(causes).not.toHaveTextContent("Aucun bien");
    expect(causes?.querySelector("a")).toHaveAttribute("href", "/fiscalite#reopen-title");
  });

  it("explains a disabled rent preparation for a missing tenant and a closed year", async () => {
    mockApi({ years: [{ id: 1, year: 2025, status: "CLOSED" }] });
    renderOperations("Biens");
    const button = await screen.findByRole("button", { name: "Préparer les loyers de l’exercice" });
    expect(button).toBeDisabled();
    const causes = document.getElementById("rents-1");
    expect(causes).toHaveTextContent("clôturé");
    expect(causes).toHaveTextContent("pas de colocataire");
    expect(causes?.querySelector('a[href="/operations/biens#colocataires-1"]')).toBeTruthy();
    expect(causes?.querySelector('a[href="/fiscalite#reopen-title"]')).toBeTruthy();
  });

  it("explains a disabled loan when no property exists", async () => {
    mockApi({ properties: [] });
    renderOperations("Emprunts");
    const button = await screen.findByRole("button", { name: "Ajouter un emprunt" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-describedby", "loan-create-causes");
    expect(document.getElementById("loan-create-causes")).toHaveTextContent("Aucun bien n’est enregistré.");
  });

  it("explains a disabled funding and settlement when no bank exists", async () => {
    mockApi({
      banks: null,
      loans: [{
        id: 1, lender: "Banque fictive", property_id: 1, initial_principal: "15000.00",
        remaining_principal: "0.00", on_balance_sheet: false, posting_path: "funding",
        monthly_payment: "62.58", monthly_insurance: "4.53", principal_account: "164000",
        interest_rate_basis_points: 1500,
      }],
    });
    renderOperations("Emprunts");
    expect(await screen.findByText(/Pas encore au bilan/)).toBeInTheDocument();
    expect(screen.queryByText(/Solde comptable/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enregistrer le déblocage" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Saisir une échéance" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Importer les échéances/)).not.toBeInTheDocument();
    expect(document.getElementById("operation-bank-causes")).toHaveTextContent("Aucun compte bancaire");
    expect(document.querySelector('a[href="/operations/banque#ajouter-banque"]')).toHaveTextContent("Ajouter un compte bancaire");
  });

  it("shows the contract capital and blocks an installment until the loan is posted", async () => {
    mockApi({
      loans: [{
        id: 2, lender: "Crédit Habitat 195k", property_id: 1, initial_principal: "195000.00",
        remaining_principal: "0.00", on_balance_sheet: false, posting_path: "funding",
        monthly_payment: "0.00", monthly_insurance: "0.00", principal_account: "164001",
        interest_rate_basis_points: 3250, start_date: "2025-06-01",
      }],
    });
    renderOperations("Emprunts");
    expect(await screen.findByText(/Capital emprunté \(contrat\) : 195[\s\u00a0\u202f]000,00 €/)).toBeInTheDocument();
    expect(screen.getByText(/Pas encore au bilan/)).toBeInTheDocument();
    expect(screen.queryByText(/Solde comptable : 0,00 €/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enregistrer le déblocage" })).toBeEnabled();
    expect(screen.queryByRole("link", { name: "Faire entrer le bien en comptabilité" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Importer les échéances/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Saisir une échéance" }));
    expect(screen.getAllByText("Aucun capital comptable à rembourser pour cet emprunt.").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("Date comptable"), { target: { value: "2025-03-01" } });
    fireEvent.change(screen.getByLabelText("Référence justificative"), { target: { value: "ECH-TEST" } });
    fireEvent.change(screen.getByLabelText("Intérêts (€)"), { target: { value: "10,00" } });
    await userEvent.click(screen.getByRole("button", { name: "Vérifier avant enregistrement" }));
    const confirm = screen.getByRole("button", { name: "Confirmer l’enregistrement" });
    expect(confirm).toBeDisabled();
    expect(confirm).toHaveAttribute("aria-describedby");
  });

  it("offers only the property entry when the loan predates the exercise", async () => {
    mockApi({
      loans: [{
        id: 3, lender: "Crédit ancien", property_id: 1, initial_principal: "15000.00",
        remaining_principal: "0.00", on_balance_sheet: false, posting_path: "property_entry",
        monthly_payment: "58.00", monthly_insurance: "0.00", principal_account: "164000",
        start_date: "2024-06-01",
      }],
    });
    renderOperations("Emprunts");
    expect(await screen.findByRole("link", { name: "Faire entrer le bien en comptabilité" })).toHaveAttribute(
      "href",
      "/immobilisations#entree-bien",
    );
    expect(screen.queryByRole("button", { name: "Enregistrer le déblocage" })).not.toBeInTheDocument();
    expect(screen.getByText(/sans déblocage/)).toBeInTheDocument();
  });

  it("keeps a repaid loan at a ledger balance of zero", async () => {
    mockApi({
      loans: [{
        id: 4, lender: "Crédit soldé", property_id: 1, initial_principal: "15000.00",
        remaining_principal: "0.00", on_balance_sheet: true, posting_path: null,
        monthly_payment: "58.00", monthly_insurance: "0.00", principal_account: "164000",
      }],
    });
    renderOperations("Emprunts");
    expect(await screen.findByText(/Solde comptable : 0,00 €/)).toBeInTheDocument();
    expect(screen.queryByText(/Pas encore au bilan/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enregistrer le déblocage" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Importer les échéances/)).not.toBeInTheDocument();
  });

  it("opens, replaces and closes an entry detail from the keyboard", async () => {
    const user = userEvent.setup();
    mockApi({
      operations: [
        {
          id: 1, kind: "EXPENSE", property_id: 1, fiscal_year_id: 1,
          date: "2025-02-01", amount: "100.00", description: "Assurance",
          counterparty: "Fournisseur", accounting_entry_id: 5,
          remaining_to_settle: "40.00", status: "POSTED",
          deductible_percentage: "80.00", fiscal_treatment: "PARTIAL",
          principal: "0.00", interest: "0.00", insurance: "0.00", other_costs: "0.00",
        },
        {
          id: 2, kind: "REVENUE", property_id: 1, fiscal_year_id: 1,
          date: "2025-03-01", amount: "800.00", description: "Loyer",
          counterparty: "Dupont", accounting_entry_id: 6,
          remaining_to_settle: "0.00", status: "SETTLED",
          deductible_percentage: "100.00", fiscal_treatment: "NONE",
          principal: "0.00", interest: "0.00", insurance: "0.00", other_costs: "0.00",
        },
      ],
      entries: {
        "5": entryFixture(5, "2025-000005", "Prime d’assurance"),
        "6": entryFixture(6, "2025-000006", "Loyer mars"),
      },
    });
    renderOperations("Transactions");
    const openers = await screen.findAllByRole("button", { name: "Voir l’écriture" });
    const first = openers[0];
    const second = openers[1];
    if (!first || !second) throw new Error("Deux boutons Voir l’écriture sont attendus.");
    const transactions = screen.getByRole("button", { name: /Transactions/ });
    expect(transactions).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();

    first.focus();
    await user.keyboard("{Enter}");
    const firstDetail = await screen.findByRole("heading", { name: "2025-000005 · Prime d’assurance" });
    expect(firstDetail.tagName).toBe("H3");
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "616000" })).toBeInTheDocument();
    expect(transactions).toHaveAttribute("aria-pressed", "true");

    const close = screen.getByRole("button", { name: "Fermer le détail de l’écriture" });
    expect(close).toHaveTextContent("Fermer");
    close.focus();
    await user.keyboard("{Enter}");
    expect(screen.queryByRole("heading", { name: "2025-000005 · Prime d’assurance" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Fermer le détail de l’écriture" })).not.toBeInTheDocument();
    expect(first).toHaveFocus();
    expect(transactions).toHaveAttribute("aria-pressed", "true");

    await user.keyboard("{Enter}");
    expect(await screen.findByRole("heading", { name: "2025-000005 · Prime d’assurance" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("heading", { name: "2025-000005 · Prime d’assurance" })).not.toBeInTheDocument();
    expect(first).toHaveFocus();
    expect(transactions).toHaveAttribute("aria-pressed", "true");

    second.focus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("heading", { name: "2025-000006 · Loyer mars" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "2025-000005 · Prime d’assurance" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Fermer le détail de l’écriture" })).toHaveLength(1);
    expect(screen.getByRole("cell", { name: "706000" })).toBeInTheDocument();
    expect(transactions).toHaveAttribute("aria-pressed", "true");

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("heading", { name: "2025-000006 · Loyer mars" })).not.toBeInTheDocument();
    expect(second).toHaveFocus();
    expect(transactions).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  });

  it("keeps the entry detail and its close button on a narrow screen", async () => {
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: /max-width:\s*(?:800|768|430)px/.test(query),
      media: query,
      onchange: null,
      addEventListener() { return undefined; },
      removeEventListener() { return undefined; },
      dispatchEvent() { return false; },
    }));
    mockApi({
      operations: [{
        id: 1, kind: "EXPENSE", property_id: 1, fiscal_year_id: 1,
        date: "2025-02-01", amount: "100.00", description: "Assurance",
        counterparty: "Fournisseur", accounting_entry_id: 5,
        remaining_to_settle: "40.00", status: "POSTED",
        deductible_percentage: "80.00", fiscal_treatment: "PARTIAL",
        principal: "0.00", interest: "0.00", insurance: "0.00", other_costs: "0.00",
      }],
      entries: { "5": entryFixture(5, "2025-000005", "Prime d’assurance") },
    });
    renderOperations("Transactions");
    await userEvent.click(await screen.findByRole("button", { name: "Voir l’écriture" }));
    expect(await screen.findByRole("list", { name: "Lignes de l’écriture" })).toBeInTheDocument();
    expect(document.querySelector("[data-mobile-variant='cards']")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Fermer le détail de l’écriture" })).toHaveTextContent("Fermer");
    expect(screen.getByRole("heading", { name: "2025-000005 · Prime d’assurance" }).tagName).toBe("H3");
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Fermer le détail de l’écriture" }));
    expect(screen.queryByRole("list", { name: "Lignes de l’écriture" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Transactions/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("saves a property without land area and reloads the recorded split", async () => {
    const saved = {
      id: 7,
      name: "Studio fictif",
      address: "1 rue des Scénarios",
      acquisition_date: "2025-01-09",
      rental_start_date: null,
      acquisition_price: "100000.00",
      acquisition_costs: "0.00",
      land_value: "20000.00",
      building_value: "80000.00",
      notes: "",
    };
    let properties: unknown[] = [];
    const fetcher = vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/ledger/setup") return response({
        activity: { activity_name: "Fictif" },
        years: [{ id: 1, year: 2025, start_date: "2025-01-01", end_date: "2025-12-31", status: "OPEN" }],
      });
      if (url === "/api/ledger/accounts") return response([]);
      if (url === "/api/operations/properties" && init?.method === "POST") {
        properties = [saved];
        return response(saved);
      }
      if (url === "/api/operations/properties") return response(properties);
      if (url === "/api/operations/properties/7/tenants") return response([]);
      if (url === "/api/operations/banks") return response([]);
      if (url === "/api/operations/loans") return response([]);
      if (url.startsWith("/api/operations?")) return response([]);
      if (url.startsWith("/api/operations/bank/transactions")) return response([]);
      return response({});
    });
    vi.stubGlobal("fetch", fetcher);
    renderOperations("Biens");
    await userEvent.click(await screen.findByRole("button", { name: "Ajouter un bien" }));
    expect(screen.getByLabelText(/Surface du terrain/)).not.toBeRequired();
    expect(screen.getByLabelText(/Prix constaté au m²/)).toHaveValue("");
    expect(screen.getByLabelText(/Prix constaté au m²/)).not.toBeRequired();
    expect(screen.getAllByText("JJ/MM/AAAA").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Date d’acquisition")).toHaveAttribute("lang", "fr");

    fireEvent.change(screen.getByLabelText("Nom du bien"), { target: { value: "Studio fictif" } });
    fireEvent.change(screen.getByLabelText("Adresse"), { target: { value: "1 rue des Scénarios" } });
    fireEvent.change(screen.getByLabelText("Date d’acquisition"), { target: { value: "2025-01-09" } });
    fireEvent.change(screen.getByLabelText("Prix d’acquisition (€)"), { target: { value: "100000,00" } });
    fireEvent.change(screen.getByLabelText("Valeur du terrain (€)"), { target: { value: "20000,00" } });
    fireEvent.change(screen.getByLabelText("Valeur du bâtiment (€)"), { target: { value: "70000,00" } });
    expect(screen.getByRole("alert")).toHaveTextContent(/de moins que le prix d’acquisition/);
    await userEvent.click(screen.getByRole("button", { name: "Vérifier avant enregistrement" }));
    expect(screen.queryByText(/Vérifiez les informations/)).not.toBeInTheDocument();
    expect(fetcher.mock.calls.some((call) => call[1]?.method === "POST")).toBe(false);

    fireEvent.change(screen.getByLabelText("Valeur du bâtiment (€)"), { target: { value: "80000,00" } });
    expect(screen.queryByText(/de moins que le prix d’acquisition/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Vérifier avant enregistrement" }));
    expect(screen.queryByText(/Surface du terrain/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Prix constaté au m²/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Confirmer l’enregistrement" }));

    expect(await screen.findByRole("heading", { name: "Studio fictif" })).toBeInTheDocument();
    const post = fetcher.mock.calls.find((call) => call[0] === "/api/operations/properties" && call[1]?.method === "POST");
    const body = JSON.parse(String(post?.[1]?.body));
    expect(body).toEqual({
      name: "Studio fictif",
      address: "1 rue des Scénarios",
      acquisition_date: "2025-01-09",
      rental_start_date: null,
      acquisition_price: "100000.00",
      acquisition_costs: "0.00",
      land_value: "20000.00",
      building_value: "80000.00",
    });
    expect(body).not.toHaveProperty("lot_m2");
    expect(body).not.toHaveProperty("price_m2");

    await userEvent.click(screen.getByRole("button", { name: "Modifier Studio fictif" }));
    expect(screen.getByLabelText("Prix d’acquisition (€)")).toHaveValue("100000.00");
    expect(screen.getByLabelText("Valeur du terrain (€)")).toHaveValue("20000.00");
    expect(screen.getByLabelText("Valeur du bâtiment (€)")).toHaveValue("80000.00");
    expect(screen.getByLabelText("Date d’acquisition")).toHaveValue("2025-01-09");
    expect(screen.queryByLabelText(/Surface du terrain/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Prix constaté au m²/)).not.toBeInTheDocument();
  });
});

function entryFixture(id: number, entryNumber: string, label: string) {
  const revenue = id === 6;
  return {
    id,
    version: 1,
    fiscal_year_id: 1,
    journal_code: "OD",
    accounting_date: "2025-02-01",
    piece_reference: "P-" + id,
    piece_date: "2025-02-01",
    label,
    status: "VALIDATED",
    entry_number: entryNumber,
    total_debit: revenue ? "800.00" : "100.00",
    total_credit: revenue ? "800.00" : "100.00",
    balanced: true,
    reversal_of_id: null,
    lines: revenue
      ? [
        { id: 1, position: 1, account_number: "411000", account_label: "Client", label: "Loyer", debit: "800.00", credit: "0.00" },
        { id: 2, position: 2, account_number: "706000", account_label: "Loyers", label: "Loyer", debit: "0.00", credit: "800.00" },
      ]
      : [
        { id: 1, position: 1, account_number: "616000", account_label: "Assurance", label: "Prime", debit: "100.00", credit: "0.00" },
        { id: 2, position: 2, account_number: "401000", account_label: "Fournisseur", label: "Dette", debit: "0.00", credit: "100.00" },
      ],
  };
}
