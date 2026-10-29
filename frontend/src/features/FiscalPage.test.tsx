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
        declarable: false,
        frozen: false,
        disclaimer: "Aucun envoi n’est effectué.",
        portal: "https://www.impots.gouv.fr/professionnel/teleprocedures-efi-ou-edi",
        exercise: { start: "2025-04-06", end: "2025-12-31" },
        declarant: { name: "Mérignac", siren: null, siret: null },
        blocking: [{ code: "SIREN_MANQUANT", message: "Indiquez le SIREN de l’activité." }],
        instructions: ["2033-B : cocher la case 018 « Formulaire déposé au titre de l’IR »."],
        depreciation_tracking: {
          accounting_depreciation: "800.00",
          capacity: "600.00",
          deducted_current: "600.00",
          deferred_current: "200.00",
          prior_used: "0.00",
          prior: [],
          remaining_total: "200.00",
        },
        liasse: {
          form: "2033-B",
          vintage: "2025",
          fields: [
            { code: "AMORT_NON_DEDUCTIBLE", form_ref: "2033-B-SD", official_case: "318", label: "Amortissements non déductibles", value: "200.00", expression: "x" },
            { code: "2031BIS_LMNP_BENEFICE", form_ref: "2031-BIS-SD", official_case: null, label: "Autres locations meublées non professionnelles — bénéfice", value: "0.00", expression: "x" },
          ],
        },
        personal_return: {
          form: "2042-C-PRO",
          status: "verified_by_cross_reference",
          lines: [
            { case: "5NA", case_declarant_2: "5OA", label: "LMNP réel — bénéfice", amount: "0.00" },
            { case: "5NY", case_declarant_2: "5OY", label: "LMNP réel — déficit", amount: "0.00" },
          ],
          prior_deficits: [],
          note: "Une seule des deux lignes porte un montant.",
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

  const calculate = screen.getByRole("button", { name: "Calculer le résultat fiscal" });
  const closeHeading = screen.getByRole("heading", { name: "Clôturer l’exercice" });
  const liasse = screen.getByRole("button", { name: "Liasse à recopier" });
  expect(calculate.compareDocumentPosition(closeHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(closeHeading.compareDocumentPosition(liasse) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Sorties figées" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Calculer le résultat fiscal" }));
  expect(await screen.findByText(/objectif LMNP atteint/i)).toBeInTheDocument();
  expect(screen.getByRole("slider", { name: /Dotation de l’année/ })).toBeInTheDocument();
  const resultRow = screen.getByText("Résultat fiscal").closest("li");
  expect(resultRow).toBeTruthy();
  expect(within(resultRow as HTMLElement).getByText("0.00 €")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Liasse à recopier" }));
  expect(await screen.findByText(/Aucun envoi n’est effectué/)).toBeInTheDocument();
  expect(screen.getByText("Pas encore prête")).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("Indiquez le SIREN");
  expect(screen.getByText(/case 018/)).toBeInTheDocument();
  expect(screen.getByText("2033-B — compte de résultat et résultat fiscal")).toBeInTheDocument();
  expect(screen.getByText("2031-bis — BIC non professionnels")).toBeInTheDocument();
  expect(screen.getByText("5NA")).toBeInTheDocument();
  expect(screen.getByText(/État de suivi des amortissements non déduits/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /PDF de recopie/ })).toHaveAttribute(
    "href",
    "/api/filing/years/1/efi.pdf",
  );
  expect(screen.queryByRole("link", { name: /Dossier de contrôle/ })).not.toBeInTheDocument();
});
