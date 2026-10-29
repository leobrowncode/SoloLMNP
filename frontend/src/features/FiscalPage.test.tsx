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
  const closing = screen.getByRole("heading", { name: "Pré-contrôle et clôture" });
  const liasse = screen.getByRole("button", { name: "Liasse à recopier" });
  expect(calculate.compareDocumentPosition(closing) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(closing.compareDocumentPosition(liasse) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(calculate).toHaveAttribute("id", "calcul-fiscal");

  fireEvent.click(screen.getByRole("button", { name: "Calculer le résultat fiscal" }));
  expect(await screen.findByText(/objectif LMNP atteint/i)).toBeInTheDocument();
  expect(screen.getByRole("slider", { name: /Dotation de l’année/ })).toBeInTheDocument();
  const resultRow = screen.getByText("Résultat fiscal").closest("li");
  expect(resultRow).toBeTruthy();
  expect(within(resultRow as HTMLElement).getByText("0.00 €")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Liasse à recopier" }));
  expect(await screen.findByText(/Aucun envoi n’est effectué/)).toBeInTheDocument();
  expect(screen.getAllByText("Recherche").length).toBeGreaterThan(0);
  expect(screen.queryByText(/Prête à recopier/)).not.toBeInTheDocument();
  expect(screen.queryByText("Pas encore prête")).not.toBeInTheDocument();
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

test("closing reloads the exercise status, the dashboard and the frozen exports", async () => {
  let phase: "open" | "ready" | "closed" = "open";
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/vintages")) {
      return response({ vintages: [{ vintage: "2025", status: "research_only", blocked: [], executable: [] }] });
    }
    if (url.endsWith("/setup")) {
      const status = phase === "closed" ? "CLOSED" : phase === "ready" ? "READY_TO_CLOSE" : "OPEN";
      return response({ years: [{ id: 1, year: 2025, status }] });
    }
    if (url.endsWith("/statements")) {
      return response({
        income_statement: {
          income: [],
          expenses: [],
          total_income: "1000.00",
          total_expenses: "1200.00",
          result: phase === "closed" ? "60.00" : "-200.00",
        },
      });
    }
    if (url.endsWith("/precheck")) {
      return response({
        blocking: false,
        year_status: phase === "closed" ? "CLOSED" : "OPEN",
        errors: [],
        warnings: [{ code: "FISCAL_RESEARCH", message: "Le calcul fiscal reste en recherche." }],
      });
    }
    if (url.endsWith("/ready") && method === "POST") {
      phase = "ready";
      return response({
        blocking: false,
        year_status: "READY_TO_CLOSE",
        errors: [],
        warnings: [{ code: "FISCAL_RESEARCH", message: "Le calcul fiscal reste en recherche." }],
      });
    }
    if (url.endsWith("/close") && method === "POST") {
      phase = "closed";
      return response({ fiscal_year_id: 1, status: "CLOSED", generation: 1 });
    }
    if (url.endsWith("/efi")) {
      return response({
        transmission: false,
        declarable: false,
        frozen: phase === "closed",
        disclaimer: "Aucun envoi n’est effectué.",
        exercise: { start: "2025-01-01", end: "2025-12-31" },
        declarant: { name: "Test", siren: "123456789", siret: null },
        blocking: [],
        instructions: [],
        liasse: { form: "2033-B", vintage: "2025", fields: [] },
        personal_return: { form: "2042-C-PRO", status: "verified_by_cross_reference", lines: [] },
      });
    }
    throw new Error(`unexpected ${method} ${url}`);
  });

  render(<FiscalPage />);
  expect(await screen.findByRole("option", { name: "2025 · ouvert" })).toBeInTheDocument();
  expect(await screen.findByText("-200.00 €")).toBeInTheDocument();
  expect(screen.getByText("Le FEC sera disponible après la clôture.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "Le calcul fiscal reste en recherche." }));
  fireEvent.click(screen.getByRole("button", { name: "Accuser et préparer la clôture" }));
  expect(await screen.findByRole("option", { name: "2025 · prêt à clôturer" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Liasse à recopier" }));
  expect(await screen.findByText(/calcul en cours/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Dossier de contrôle/ })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Confirmer la clôture" }));
  expect(await screen.findByRole("option", { name: "2025 · clôturé" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Télécharger le FEC" })).toHaveAttribute(
    "href",
    "/api/filing/years/1/fec",
  );
  expect(screen.queryByText("Le FEC sera disponible après la clôture.")).not.toBeInTheDocument();
  expect(await screen.findByText(/montants figés à la clôture/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Dossier de contrôle/ })).toBeInTheDocument();
  expect(screen.getByText("60.00 €")).toBeInTheDocument();
  expect(screen.queryByText("-200.00 €")).not.toBeInTheDocument();
  expect(screen.getByText(/Exercice clôturé/)).toBeInTheDocument();
});

test("a refused close keeps the ready exercise and explains the failure", async () => {
  let phase: "open" | "ready" = "open";
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/vintages")) {
      return response({ vintages: [] });
    }
    if (url.endsWith("/setup")) {
      return response({
        years: [{ id: 1, year: 2025, status: phase === "ready" ? "READY_TO_CLOSE" : "OPEN" }],
      });
    }
    if (url.endsWith("/statements")) {
      return response({
        income_statement: {
          income: [], expenses: [], total_income: "0.00", total_expenses: "0.00", result: "0.00",
        },
      });
    }
    if (url.endsWith("/precheck") || (url.endsWith("/ready") && method === "POST")) {
      if (url.endsWith("/ready")) phase = "ready";
      return response({
        blocking: false,
        year_status: phase === "ready" ? "READY_TO_CLOSE" : "OPEN",
        errors: [],
        warnings: [{ code: "FISCAL_RESEARCH", message: "Le calcul fiscal reste en recherche." }],
      });
    }
    if (url.endsWith("/close")) {
      return response({ detail: { message: "La clôture a été refusée." } }, 409);
    }
    throw new Error(`unexpected ${method} ${url}`);
  });

  render(<FiscalPage />);
  expect(await screen.findByRole("option", { name: "2025 · ouvert" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "Le calcul fiscal reste en recherche." }));
  fireEvent.click(screen.getByRole("button", { name: "Accuser et préparer la clôture" }));
  expect(await screen.findByRole("option", { name: "2025 · prêt à clôturer" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirmer la clôture" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("La clôture a été refusée.");
  expect(screen.getByRole("option", { name: "2025 · prêt à clôturer" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "2025 · clôturé" })).not.toBeInTheDocument();
  expect(screen.getByText("Le FEC sera disponible après la clôture.")).toBeInTheDocument();
  expect(screen.queryByText(/Exercice clôturé/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Confirmer la clôture" })).toBeEnabled();
});

test("reopening a closed exercise reloads open status and frozen exports", async () => {
  let phase: "open" | "closed" = "closed";
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/vintages")) {
      return response({ vintages: [] });
    }
    if (url.endsWith("/setup")) {
      return response({
        years: [{ id: 1, year: 2025, status: phase === "closed" ? "CLOSED" : "OPEN" }],
      });
    }
    if (url.endsWith("/statements")) {
      return response({
        income_statement: {
          income: [], expenses: [], total_income: "0.00", total_expenses: "0.00", result: "0.00",
        },
      });
    }
    if (url.endsWith("/precheck")) {
      return response({
        blocking: false,
        year_status: phase === "closed" ? "CLOSED" : "OPEN",
        errors: [],
        warnings: [],
      });
    }
    if (url.endsWith("/reopen") && method === "POST") {
      phase = "open";
      return response({ fiscal_year_id: 1, status: "OPEN" });
    }
    throw new Error(`unexpected ${method} ${url}`);
  });

  render(<FiscalPage />);
  expect(await screen.findByRole("option", { name: "2025 · clôturé" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  expect(await screen.findByRole("heading", { name: "Réouvrir l’exercice" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/Motif de la réouverture/), {
    target: { value: "Correction test après clôture pour réouverture guidée." },
  });
  fireEvent.change(screen.getByLabelText(/Confirmation/), {
    target: { value: "ROUVRIR" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Réouvrir l’exercice" }));
  expect(await screen.findByRole("option", { name: "2025 · ouvert" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Réouvrir l’exercice" })).not.toBeInTheDocument();
  expect(screen.getByText("Le FEC sera disponible après la clôture.")).toBeInTheDocument();
});
