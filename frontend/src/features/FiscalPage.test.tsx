import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import FiscalPage from "./FiscalPage";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

test("shows a simple LMNP charges dashboard with help tips and EFI disclaimer", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/vintages")) {
      return response({
        vintages: [{
          vintage: "2025",
          status: "research_only",
          blocked: [],
          scope: ["RULE-LMNP-BIC-001"],
          executable: [],
        }],
      });
    }
    if (url.endsWith("/setup")) {
      return response({ years: [{ id: 1, year: 2025, status: "OPEN" }] });
    }
    if (url.endsWith("/statements")) {
      return response({
        income_statement: {
          income: [{ account_number: "706000", label: "Loyers", amount: "1000.00" }],
          expenses: [
            { account_number: "615000", label: "Entretien", amount: "400.00" },
            { account_number: "681100", label: "Dotations", amount: "800.00" },
          ],
          total_income: "1000.00",
          total_expenses: "1200.00",
          result: "-200.00",
        },
      });
    }
    if (url.includes("/api/fiscal/years/1") && init?.method === "POST") {
      return response({
        status: "research_only",
        declarable: false,
        accounting_result: "-200.00",
        fiscal_result: "0.00",
        deductible_depreciation: "600.00",
        unused_depreciation: "200.00",
        tax_loss: "0.00",
        non_deductible: "0.00",
        details: {
          operating_income: "1000.00",
          other_charges: "400.00",
          accounting_depreciation: "800.00",
          capacity: "600.00",
          current_deductible_depreciation: "600.00",
          prior_depreciation_used: "0.00",
          prior_tax_loss_used: "0.00",
          goal_hint: "Résultat fiscal à 0 € : objectif LMNP atteint pour l’impôt BIC de l’activité.",
          prior_carry_forward_use: { status: "enabled", depreciation: [], tax_loss: [] },
        },
      });
    }
    if (url.includes("/efi")) {
      return response({
        transmission: false,
        disclaimer: "Aucun envoi n’est effectué.",
        portal: "https://www.impots.gouv.fr/professionnel/teleprocedures-efi-ou-edi",
        liasse: { form: "2033-B", vintage: "2025", fields: [] },
        personal_return: {
          form: "2042-C-PRO",
          official_case: null,
          status: "case_not_verified",
          amount: "0.00",
        },
      });
    }
    return response({
      transmission: false,
      disclaimer: "Aucun envoi n’est effectué.",
      personal_return: {
        form: "2042-C-PRO",
        official_case: null,
        status: "case_not_verified",
        amount: "0.00",
      },
    });
  });

  render(<FiscalPage />);
  expect(await screen.findByRole("heading", { name: /Charges & amortissements LMNP/ })).toBeInTheDocument();
  expect(screen.getByText(/résultat fiscal proche de 0/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Aide : Plafond/ })).toBeInTheDocument();
  expect(await screen.findByText("Dotation — plafonnée fiscalement")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Calculer le résultat fiscal" }));
  expect(await screen.findByText(/objectif LMNP atteint/i)).toBeInTheDocument();
  const resultRow = screen.getByText("Résultat fiscal").closest("li");
  expect(resultRow).toBeTruthy();
  expect(within(resultRow as HTMLElement).getByText("0.00 €")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Liasse à recopier" }));
  expect(await screen.findByText(/Aucun envoi n’est effectué/)).toBeInTheDocument();
  expect(screen.getByText(/Télétransmission : non/)).toBeInTheDocument();
  expect(screen.getByText(/non vérifiée/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /PDF de recopie/ })).toHaveAttribute(
    "href",
    "/api/filing/years/1/efi.pdf",
  );
});
