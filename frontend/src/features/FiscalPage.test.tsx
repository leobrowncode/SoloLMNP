import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import FiscalPage from "./FiscalPage";

afterEach(() => vi.restoreAllMocks());

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

const notComputed = () => response({
  detail: {
    code: "FISCAL_NOT_COMPUTED",
    message: "Aucun calcul fiscal n’est enregistré pour cet exercice.",
  },
}, 404);

function slot(posture: "provisoire" | "bloquee" | "finale") {
  const label = posture === "finale" ? "Finale" : posture === "provisoire" ? "Provisoire" : "Bloquée";
  return { posture, label, download: posture !== "bloquee" };
}

function exportBody(closed = false, liasse: "provisoire" | "bloquee" | "finale" = closed ? "provisoire" : "bloquee") {
  const liasseSlot = slot(liasse);
  const fecPosture = !closed || liasse === "bloquee" ? "bloquee" : liasse === "finale" ? "finale" : "provisoire";
  const fecSlot = slot(fecPosture);
  const prerequisites = [];
  if (liasse === "bloquee") {
    prerequisites.push({
      code: "SIREN_MANQUANT",
      message: "Indiquez le SIREN de l’activité.",
      export: "liasse",
      action: { label: "Renseigner le SIREN", href: "/comptabilite/brouillons#identite-liasse" },
    });
  }
  if (!closed) {
    prerequisites.push({
      code: "YEAR_NOT_CLOSED",
      message: "Le FEC final et le dossier de contrôle exigent un exercice clôturé.",
      export: "fec",
      action: { label: "Clôturer l’exercice", href: "/fiscalite#close-title" },
    });
  }
  return {
    output_status: liasse === "finale" ? "declarable" : "recherche",
    output_label: liasse === "finale" ? "Déclarable" : "Recherche",
    exports: { liasse: liasseSlot, pdf: liasseSlot, fec: fecSlot, archive: fecSlot },
    prerequisites,
  };
}

function isFiscalRead(url: string, method: string) {
  return method === "GET" && /\/api\/fiscal\/years\/\d+$/.test(url);
}

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
    if (isFiscalRead(url, init?.method ?? "GET")) return notComputed();
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
    if (url.endsWith("/exports")) return response(exportBody(false, "bloquee"));
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
        warnings: [
          { code: "RESEARCH_ONLY", level: "info", message: "Feuille de recopie : aucun envoi." },
          { code: "CVAE_BASE_SEULE", level: "warning", message: "La case 117 est une base, pas une cotisation." },
          { code: "ECART_A_RELIRE", level: "error", message: "Écart à relire avant recopie." },
        ],
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
  const resultRow = screen.getByRole("button", { name: "Aide : Résultat fiscal" }).closest("li");
  expect(resultRow).toBeTruthy();
  expect(within(resultRow as HTMLElement).getByText("0,00 €")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Liasse à recopier" }));
  const sheet = await screen.findByText((_, node) => (
    node?.classList.contains("fiscal-goal") === true
    && (node.textContent ?? "").includes("Aucun envoi n’est effectué")
  ));
  expect(sheet).toBeInTheDocument();
  expect(document.getElementById("sorties-figees")).toHaveTextContent("Aucun envoi n’est effectué");
  expect(screen.getAllByText("Recherche").length).toBeGreaterThan(0);
  expect(screen.queryByText(/Prête à recopier/)).not.toBeInTheDocument();
  expect(screen.queryByText("Pas encore prête")).not.toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("Indiquez le SIREN");
  expect(screen.getByText(/case 018/)).toBeInTheDocument();
  expect(screen.getByText("2033-B — compte de résultat et résultat fiscal")).toBeInTheDocument();
  expect(screen.getByText("2031-bis — BIC non professionnels")).toBeInTheDocument();
  expect(screen.getByText("5NA")).toBeInTheDocument();
  expect(screen.getByText(/État de suivi des amortissements non déduits/)).toBeInTheDocument();
  const warningList = screen.getByRole("list", { name: "Avertissements de la liasse" });
  expect(within(warningList).getByText("Information")).toBeInTheDocument();
  expect(within(warningList).getByText("Feuille de recopie : aucun envoi.")).toBeInTheDocument();
  expect(within(warningList).getByText("Avertissement")).toBeInTheDocument();
  expect(within(warningList).getByText("La case 117 est une base, pas une cotisation.")).toBeInTheDocument();
  expect(within(warningList).getByText("Erreur")).toBeInTheDocument();
  expect(within(warningList).getByText("Écart à relire avant recopie.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Télécharger le PDF de recopie" })).toBeDisabled();
  expect(screen.getAllByText("Bloquée").length).toBeGreaterThan(0);
  expect(screen.getByText(/exigent un exercice clôturé/)).toBeInTheDocument();
  expect(document.querySelector('a[href*="/api/filing"]')).toBeNull();
  expect(screen.queryByRole("link", { name: /Dossier de contrôle/ })).not.toBeInTheDocument();
});

test("closing reloads the exercise status, the dashboard and the frozen exports", async () => {
  let phase: "open" | "ready" | "closed" = "open";
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (isFiscalRead(url, method)) return notComputed();
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
    if (url.endsWith("/exports")) return response(exportBody(phase === "closed"));
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
  expect(await screen.findByText("-200,00 €")).toBeInTheDocument();
  expect(await screen.findByText(/exigent un exercice clôturé/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Télécharger le FEC" })).toBeDisabled();

  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "Le calcul fiscal reste en recherche." }));
  fireEvent.click(screen.getByRole("button", { name: "Accuser et préparer la clôture" }));
  expect(await screen.findByRole("option", { name: "2025 · prêt à clôturer" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Liasse à recopier" }));
  expect(await screen.findByText(/calcul en cours/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Dossier de contrôle/ })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Télécharger le dossier de contrôle" })).toBeDisabled();

  fireEvent.click(screen.getByRole("button", { name: "Confirmer la clôture" }));
  expect(await screen.findByRole("option", { name: "2025 · clôturé" })).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "Télécharger le FEC" })).toBeEnabled());
  expect(screen.queryByText(/exigent un exercice clôturé/)).not.toBeInTheDocument();
  expect(await screen.findByText(/montants figés à la clôture/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Télécharger le dossier de contrôle" })).toBeEnabled();
  expect(screen.queryByText("Finale")).not.toBeInTheDocument();
  expect(screen.getByText("Même statut pour le calcul, la liasse et les exports.")).toBeInTheDocument();
  expect(screen.getAllByText(/Document de travail, à vérifier/).length).toBeGreaterThan(0);
  expect(document.querySelector('a[href*="/api/filing"]')).toBeNull();
  expect(screen.getByText("60,00 €")).toBeInTheDocument();
  expect(screen.queryByText("-200,00 €")).not.toBeInTheDocument();
  expect(screen.getByText(/Exercice clôturé/)).toBeInTheDocument();
});

test("a refused close keeps the ready exercise and explains the failure", async () => {
  let phase: "open" | "ready" = "open";
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (isFiscalRead(url, method)) return notComputed();
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
    if (url.endsWith("/exports")) return response(exportBody(false));
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
  expect(screen.getByText(/exigent un exercice clôturé/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Télécharger le FEC" })).toBeDisabled();
  expect(screen.queryByText(/Exercice clôturé/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Confirmer la clôture" })).toBeEnabled();
});

test("reopening a closed exercise reloads open status and frozen exports", async () => {
  let phase: "open" | "closed" = "closed";
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (isFiscalRead(url, method)) return notComputed();
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
    if (url.endsWith("/exports")) return response(exportBody(phase === "closed"));
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
  expect(await screen.findByText(/exigent un exercice clôturé/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Télécharger le FEC" })).toBeDisabled();
});

const STORED = "a".repeat(64);
const MOVED = "b".repeat(64);

function storedComputation(current = STORED, fiscal = "12.34") {
  return {
    status: "research_only",
    declarable: false,
    accounting_result: "-200.00",
    fiscal_result: fiscal,
    deductible_depreciation: "600.00",
    unused_depreciation: "200.00",
    tax_loss: "0.00",
    non_deductible: "0.00",
    computed_at: "2026-03-02T08:15:00Z",
    ledger_sha256: STORED,
    current_ledger_sha256: current,
    details: {
      operating_income: "1000.00",
      other_charges: "400.00",
      accounting_depreciation: "800.00",
      capacity: "600.00",
      current_deductible_depreciation: "600.00",
      prior_depreciation_used: "0.00",
      prior_tax_loss_used: "0.00",
      goal_hint: `Lecture du résultat ${fiscal}.`,
      prior_carry_forward_use: { status: "enabled", depreciation: [], tax_loss: [] },
    },
  };
}

function fiscalScreen(handler: (url: string, method: string) => Response | null) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const extra = handler(url, method);
    if (extra) return extra;
    if (url.endsWith("/vintages")) {
      return response({ vintages: [{ vintage: "2025", status: "research_only", blocked: [], executable: [] }] });
    }
    if (url.endsWith("/setup")) return response({ years: [{ id: 1, year: 2025, status: "OPEN" }] });
    if (url.endsWith("/statements")) {
      return response({
        income_statement: {
          income: [],
          expenses: [],
          total_income: "1000.00",
          total_expenses: "1200.00",
          result: "-200.00",
        },
      });
    }
    if (url.endsWith("/precheck")) {
      return response({ blocking: false, year_status: "OPEN", errors: [], warnings: [] });
    }
    if (url.endsWith("/exports")) return response(exportBody(false, "provisoire"));
    throw new Error(`unexpected ${method} ${url}`);
  });
}

test("reloads the last calculation with its date and ledger fingerprint", async () => {
  fiscalScreen((url, method) => (
    isFiscalRead(url, method) ? response(storedComputation()) : null
  ));
  render(<FiscalPage />);
  expect(await screen.findByText("12,34 €")).toBeInTheDocument();
  expect(document.querySelector("time")).toHaveAttribute("datetime", "2026-03-02T08:15:00Z");
  expect(screen.getByText(/Calcul du/)).toBeInTheDocument();
  expect(screen.getByText(`Empreinte ${STORED}`)).toBeInTheDocument();
  expect(screen.getByText("Correspond au ledger")).toBeInTheDocument();
  expect(screen.queryByText("Obsolète")).not.toBeInTheDocument();
  expect(screen.getAllByText("Recherche").length).toBeGreaterThan(0);
  expect(screen.getByText(/pas une base de déclaration/)).toBeInTheDocument();
  expect(screen.queryByText(/Prête à recopier/)).not.toBeInTheDocument();
});

test("marks an invalidated calculation obsolete even when the fingerprints still match", async () => {
  fiscalScreen((url, method) => (
    isFiscalRead(url, method) ? response({ ...storedComputation(), invalidated: true }) : null
  ));
  render(<FiscalPage />);
  expect(await screen.findByText("Obsolète")).toBeInTheDocument();
  expect(screen.getByText("12,34 €")).toBeInTheDocument();
  expect(screen.queryByText("Correspond au ledger")).not.toBeInTheDocument();
});

test("marks a stored result obsolete when the structuring fingerprint differs", async () => {
  fiscalScreen((url, method) => (
    isFiscalRead(url, method)
      ? response({
        ...storedComputation(),
        structuring_sha256: STORED,
        current_structuring_sha256: MOVED,
      })
      : null
  ));
  render(<FiscalPage />);
  expect(await screen.findByText("Obsolète")).toBeInTheDocument();
  expect(screen.getByText("12,34 €")).toBeInTheDocument();
  expect(screen.queryByText("Correspond au ledger")).not.toBeInTheDocument();
});

test("marks a stored result obsolete as soon as the ledger fingerprint differs", async () => {
  fiscalScreen((url, method) => (
    isFiscalRead(url, method) ? response(storedComputation(MOVED)) : null
  ));
  render(<FiscalPage />);
  expect(await screen.findByText("Obsolète")).toBeInTheDocument();
  expect(screen.getByText("12,34 €")).toBeInTheDocument();
  expect(screen.getByText(`Empreinte ${STORED}`)).toBeInTheDocument();
  expect(screen.queryByText("Correspond au ledger")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Calculer le résultat fiscal" })).toBeEnabled();
});

test("a failed recalculation drops the previous result and a later success replaces it", async () => {
  let attempts = 0;
  fiscalScreen((url, method) => {
    if (isFiscalRead(url, method)) return response(storedComputation());
    if (url.includes("/api/fiscal/years/1") && method === "POST") {
      attempts += 1;
      if (attempts === 1) {
        return response({ detail: { message: "La réintégration dépasse la charge." } }, 422);
      }
      return response(storedComputation(STORED, "56.78"));
    }
    return null;
  });
  render(<FiscalPage />);
  expect(await screen.findByText("12,34 €")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Calculer le résultat fiscal" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("La réintégration dépasse la charge.");
  expect(screen.queryByText("12,34 €")).not.toBeInTheDocument();
  expect(screen.queryByText("Correspond au ledger")).not.toBeInTheDocument();
  expect(screen.queryByText("Obsolète")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Calculer le résultat fiscal" }));
  expect(await screen.findByText("56,78 €")).toBeInTheDocument();
  expect(screen.getByText("Correspond au ledger")).toBeInTheDocument();
  expect(screen.queryByText("Obsolète")).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("a failed export read can be retried and a later failure keeps the posture cards", async () => {
  let exportsFailed = true;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (isFiscalRead(url, method)) return notComputed();
    if (url.endsWith("/vintages")) {
      return response({ vintages: [{ vintage: "2025", status: "research_only", blocked: [], executable: [] }] });
    }
    if (url.endsWith("/setup")) return response({ years: [{ id: 1, year: 2025, status: "OPEN" }] });
    if (url.endsWith("/statements")) {
      return response({
        income_statement: { income: [], expenses: [], total_income: "0.00", total_expenses: "0.00", result: "0.00" },
      });
    }
    if (url.endsWith("/exports")) {
      if (exportsFailed) {
        return response({ detail: { code: "EXPORTS_UNAVAILABLE", message: "Les sorties n’ont pas pu être lues." } }, 503);
      }
      return response(exportBody(false, "bloquee"));
    }
    if (url.includes("/api/fiscal/years/1") && method === "POST") {
      exportsFailed = true;
      return response({
        status: "computed", declarable: false, accounting_result: "0.00", fiscal_result: "0.00",
        deductible_depreciation: "0.00", unused_depreciation: "0.00", tax_loss: "0.00", non_deductible: "0.00",
      });
    }
    throw new Error(`unexpected ${method} ${url}`);
  });
  render(<FiscalPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Les sorties n’ont pas pu être lues.");
  expect(screen.queryByText(/Chargement des sorties/)).not.toBeInTheDocument();
  expect(screen.queryByText("Bloquée")).not.toBeInTheDocument();
  exportsFailed = false;
  fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
  expect(await screen.findAllByText("Bloquée")).not.toHaveLength(0);
  expect(document.querySelector("[data-posture='bloquee']")).not.toBeNull();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();

  exportsFailed = true;
  fireEvent.click(screen.getByRole("button", { name: "Calculer le résultat fiscal" }));
  expect(await screen.findByText(/peuvent être périmées/)).toBeInTheDocument();
  expect(screen.getAllByText("Bloquée").length).toBeGreaterThan(0);
  expect(screen.queryByText(/Chargement des sorties/)).not.toBeInTheDocument();
  exportsFailed = false;
  fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
  expect(await screen.findByText(/exigent un exercice clôturé/)).toBeInTheDocument();
  expect(screen.queryByText(/peuvent être périmées/)).not.toBeInTheDocument();
});

test("wires every fiscal help control as an accessible popover", async () => {
  const user = userEvent.setup();
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/vintages")) {
      return response({ vintages: [{ vintage: "2025", status: "research_only", blocked: [], executable: [] }] });
    }
    if (url.endsWith("/setup")) return response({ years: [{ id: 1, year: 2025, status: "OPEN" }] });
    if (url.endsWith("/statements")) {
      return response({
        income_statement: {
          income: [],
          expenses: [{ account_number: "615000", label: "Entretien", amount: "400.00" }],
          total_income: "1000.00",
          total_expenses: "1200.00",
          result: "-200.00",
        },
      });
    }
    if (isFiscalRead(url, method)) return notComputed();
    if (url.includes("/api/fiscal/years/1") && method === "POST") {
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
          goal_hint: "Résultat fiscal à 0 €.",
          prior_carry_forward_use: { status: "enabled", depreciation: [], tax_loss: [] },
        },
      });
    }
    if (url.endsWith("/exports")) return response(exportBody(false, "bloquee"));
    return response({});
  });

  render(<FiscalPage />);
  expect(await screen.findByRole("heading", { name: /Loyers & charges comptabilisés/ })).toBeInTheDocument();
  const triggers = screen.getAllByRole("button", { name: /^Aide :/ });
  expect(triggers.length).toBeGreaterThanOrEqual(12);
  const ids = new Set<string>();
  for (const trigger of triggers) {
    expect(trigger).toHaveAccessibleName();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    const controls = trigger.getAttribute("aria-controls");
    expect(controls).toBeTruthy();
    expect(trigger).toHaveAttribute("aria-describedby", controls);
    expect(ids.has(controls ?? "")).toBe(false);
    ids.add(controls ?? "");
    const panel = document.getElementById(controls ?? "");
    expect(panel).toHaveAttribute("role", "tooltip");
    expect(panel).toHaveAttribute("hidden");
  }
  expect(document.querySelectorAll(".help-tip").length).toBe(triggers.length);

  const beforeCompute = triggers.length;
  await user.click(screen.getByRole("button", { name: "Calculer le résultat fiscal" }));
  expect(await screen.findByText(/Résultat fiscal à 0 €/)).toBeInTheDocument();
  const after = screen.getAllByRole("button", { name: /^Aide :/ });
  expect(after.length).toBeGreaterThan(beforeCompute);
  for (const trigger of after) {
    const controls = trigger.getAttribute("aria-controls");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveAttribute("aria-describedby", controls);
    expect(document.getElementById(controls ?? "")).toHaveAttribute("role", "tooltip");
  }

  const plafond = screen.getByRole("button", { name: "Aide : Plafond" });
  await user.click(plafond);
  expect(plafond).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("tooltip")).toHaveTextContent(/ne peut pas dépasser/);
  await user.keyboard("{Escape}");
  expect(plafond).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
});

test("shows carry-forward balances and a blocked rule reason", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/vintages")) {
      return response({
        vintages: [{
          vintage: "2025",
          status: "research_only",
          output_label: "Recherche",
          blocked: [{
            id: "RULE-BLOCKED-156-BIS-001",
            blocking_reason: "Le 1° bis ne s’applique pas à la location meublée.",
          }],
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
          income: [],
          expenses: [],
          total_income: "0.00",
          total_expenses: "0.00",
          result: "0.00",
        },
      });
    }
    if (url.endsWith("/exports")) return response(exportBody(false, "bloquee"));
    if (isFiscalRead(url, method)) {
      return response({
        status: "research_only",
        declarable: false,
        accounting_result: "-200.00",
        fiscal_result: "0.00",
        deductible_depreciation: "600.00",
        unused_depreciation: "200.00",
        tax_loss: "0.00",
        non_deductible: "0.00",
        output_label: "Recherche",
        details: {
          operating_income: "1000.00",
          other_charges: "400.00",
          accounting_depreciation: "800.00",
          capacity: "600.00",
          current_deductible_depreciation: "600.00",
          prior_depreciation_used: "0.00",
          prior_tax_loss_used: "0.00",
          goal_hint: "Résultat fiscal à 0 €.",
          prior_carry_forward_use: { status: "enabled", depreciation: [], tax_loss: [] },
          carry_registers: {
            depreciation: {
              horizon_years: null,
              expires: false,
              rows: [{ origin_year: 2025, created: "200.00", used: "0.00", expired: "0.00", remaining: "200.00" }],
              totals: { created: "200.00", used: "0.00", expired: "0.00", remaining: "200.00" },
            },
            tax_loss: {
              horizon_years: 10,
              expires: true,
              rows: [{ origin_year: 2025, created: "0.00", used: "0.00", expired: "0.00", remaining: "0.00" }],
              totals: { created: "0.00", used: "0.00", expired: "0.00", remaining: "0.00" },
            },
          },
        },
      });
    }
    return response({});
  });

  const user = userEvent.setup();
  render(<FiscalPage />);
  expect(await screen.findByText("Amortissements non déduits (art. 39 C, II)")).toBeInTheDocument();
  expect(screen.getByText("Déficits LMNP (art. 156, I, 1° ter)")).toBeInTheDocument();
  expect(screen.getByText("Pas d’échéance")).toBeInTheDocument();
  expect(screen.getByText("Échéance : 10 ans")).toBeInTheDocument();
  await user.click(screen.getByText("Millésimes chargés (technique)"));
  expect(
    screen.getByText(
      "RULE-BLOCKED-156-BIS-001 — Le 1° bis ne s’applique pas à la location meublée.",
    ),
  ).toBeInTheDocument();
});
