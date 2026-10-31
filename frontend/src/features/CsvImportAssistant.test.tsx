import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { renderWithRouter } from "../routing/testPage";
import CsvImportAssistant from "./CsvImportAssistant";

const CSV = [
  "Nature;Date;Type;Tiers;Montant;Libellé;Référence de pièce;Déjà payée",
  "Recette;15/03/2025;LOY;Dupont;800,00;Loyer mars;LOY-1;oui",
  "Dépense;99/99/2025;ASS;Assureur;100,00;Date impossible;ASS-1;non",
].join("\n");

const preview = {
  profile: "operations",
  ready: true,
  delimiter: ";",
  headers: ["Nature", "Date", "Déjà payée"],
  fields: [
    { key: "description", label: "Libellé", required: true, help: "" },
    { key: "amount", label: "Montant", required: true, help: "" },
  ],
  mapping: { description: "Libellé", amount: "Montant", paid: "Déjà payée" },
  issues: [],
  rows: [
    {
      line: 2,
      status: "valid",
      importable: true,
      duplicate: false,
      display: { description: "Loyer mars", amount: "800,00" },
      issues: [],
      warnings: [],
      suggested_account: null,
    },
    {
      line: 3,
      status: "error",
      importable: false,
      duplicate: false,
      display: { description: "Date impossible", amount: "100,00", date: "99/99/2025" },
      issues: [{
        code: "CSV_INVALID",
        message: "Date invalide dans « Date ».",
        field: "date",
        column: "Date",
        value: "99/99/2025",
        correction: "Saisissez une date au format JJ/MM/AAAA, par exemple 05/03/2026.",
        line: 3,
      }],
      warnings: [],
      suggested_account: null,
    },
  ],
  summary: { valid: 1, duplicate: 0, warning: 0, error: 1, count: 2, importable: 1 },
  rejects_csv: "",
  loan_reference: null,
  imported: 0,
};

function renderAssistant(missingBank = false) {
  const commits: { body: string; key: string | null }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    if (path.endsWith("/imports/inspect")) {
      return json({
        delimiter: ";",
        headers: preview.headers,
        fields: { bank: [], operations: preview.fields, loan_payments: [] },
        suggestions: { bank: {}, operations: preview.mapping, loan_payments: {} },
      });
    }
    if (path.endsWith("/imports/operations/preview")) return json(preview);
    if (path.endsWith("/imports/operations/commit")) {
      commits.push({
        body: String(init?.body ?? ""),
        key: new Headers(init?.headers).get("Idempotency-Key"),
      });
      return json({
        imported: 1,
        batch: {
          idempotency_key: "operations-csv-1",
          replayed: false,
          posted_count: 1,
          rejected_count: 1,
          skipped_count: 0,
          items: [],
        },
      });
    }
    return json({});
  }));
  renderWithRouter(
    <CsvImportAssistant
      profile="operations"
      summaryTitle="Importer depuis Google Sheets ou un CSV"
      intro="Collez les justificatifs."
      contentLabel="Lignes collées ou contenu CSV"
      textareaId="import-operations"
      anchor="/operations/transactions#import-operations"
      causeId="operation-preview-causes"
      postCauseId="operation-post-causes"
      previewLabel="Prévisualiser les justificatifs"
      commitLabel="Comptabiliser les justificatifs"
      busy={false}
      action={(fn) => { void fn(); }}
      missingBank={missingBank}
      context={{ property_id: 1, fiscal_year_id: 1, bank_account_id: missingBank ? null : 1 }}
      onImported={() => undefined}
    />,
    "/operations/transactions",
    "/operations/:tab",
  );
  return commits;
}

function json(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  }));
}

test("paid lines without a bank are blocked before the preview", async () => {
  renderAssistant(true);
  await userEvent.click(screen.getByText("Importer depuis Google Sheets ou un CSV"));
  fireEvent.change(screen.getByLabelText("Lignes collées ou contenu CSV"), { target: { value: CSV } });
  expect(screen.getByText("Choisissez le compte bancaire des lignes déjà payées.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Prévisualiser les justificatifs" })).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Comptabiliser les justificatifs" })).not.toBeInTheDocument();
});

test("rejects stay in a short list and posting waits for an explicit choice", async () => {
  const commits = renderAssistant(false);
  await userEvent.click(screen.getByText("Importer depuis Google Sheets ou un CSV"));
  fireEvent.change(screen.getByLabelText("Lignes collées ou contenu CSV"), { target: { value: CSV } });
  await userEvent.click(screen.getByRole("button", { name: "Prévisualiser les justificatifs" }));
  expect(await screen.findByText("2 lignes : 1 valide, 1 rejet.")).toBeInTheDocument();
  const rejects = screen.getByRole("list", { name: "Lignes rejetées" });
  expect(rejects).toHaveTextContent("Ligne 3, Date : Date invalide dans « Date ».");
  expect(rejects).toHaveTextContent("99/99/2025");
  expect(screen.getByRole("list", { name: "Lignes prêtes" })).toHaveTextContent("Loyer mars");
  expect(screen.queryByRole("table", { name: "Aperçu de l’import" })).not.toBeInTheDocument();
  const post = screen.getByRole("button", { name: "Comptabiliser les justificatifs" });
  expect(post).toBeDisabled();
  const partial = screen.getByRole("button", { name: "Importer uniquement la ligne valide" });
  expect(partial).toBeDisabled();
  await userEvent.click(screen.getByRole("radio", { name: "Importer uniquement la ligne valide" }));
  expect(partial).toBeEnabled();
  expect(post).toBeDisabled();
  await userEvent.click(partial);
  expect(commits).toHaveLength(1);
  expect(commits[0]?.body).toContain("\"import_valid_only\":true");
  expect(commits[0]?.key).toMatch(/^[A-Za-z0-9_-]{8,80}$/);
  expect(await screen.findByText(/1 ligne comptabilisée/)).toBeInTheDocument();
  expect(screen.getByText(/1 ligne rejetée n’a pas été comptabilisée/)).toBeInTheDocument();
});

test("a failed inspect is shown instead of being swallowed", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
    detail: { code: "CSV_INVALID", message: "Le fichier n’a pas pu être lu." },
  }), { status: 422, headers: { "Content-Type": "application/json" } })));
  renderWithRouter(
    <CsvImportAssistant
      profile="operations"
      summaryTitle="Importer depuis Google Sheets ou un CSV"
      intro="Collez les justificatifs."
      contentLabel="Lignes collées ou contenu CSV"
      textareaId="import-operations"
      anchor="/operations/transactions#import-operations"
      causeId="operation-preview-causes"
      postCauseId="operation-post-causes"
      previewLabel="Prévisualiser les justificatifs"
      commitLabel="Comptabiliser les justificatifs"
      busy={false}
      action={(fn) => { void fn(); }}
      context={{ property_id: 1, fiscal_year_id: 1, bank_account_id: 1 }}
      onImported={() => undefined}
    />,
    "/operations/transactions",
    "/operations/:tab",
  );
  await userEvent.click(screen.getByText("Importer depuis Google Sheets ou un CSV"));
  fireEvent.change(screen.getByLabelText("Lignes collées ou contenu CSV"), { target: { value: "Nature;Date\n" } });
  expect(await screen.findByRole("alert")).toHaveTextContent("Le fichier n’a pas pu être lu.");
});

test("loan payment rejects are one alert per line, above the table", async () => {
  const loanPreview = {
    ...preview,
    profile: "loan_payments",
    summary: { valid: 0, duplicate: 0, warning: 0, error: 1, count: 1, importable: 0 },
    rows: [{
      line: 2,
      status: "error",
      importable: false,
      duplicate: false,
      suggested_account: null,
      display: { loan_reference: "085644F", due_date: "05/03/2025", principal: "100,00", amount: "999,00" },
      issues: [{
        code: "SPLIT_MISMATCH",
        message: "La ventilation ne correspond pas au total.",
        line: 2,
        column: "Total",
        value: "999,00",
        correction: "Alignez le total sur la ventilation.",
      }],
      warnings: [],
    }],
    issues: [],
  };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = String(url);
    if (path.endsWith("/imports/inspect")) {
      return new Response(JSON.stringify({
        delimiter: ";",
        headers: loanPreview.headers,
        fields: { loan_payments: loanPreview.fields },
        suggestions: { loan_payments: {} },
      }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (path.endsWith("/imports/loan_payments/preview")) {
      return new Response(JSON.stringify(loanPreview), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
  }));
  renderWithRouter(
    <CsvImportAssistant
      profile="loan_payments"
      summaryTitle="Importer les échéances"
      intro="Collez l’échéancier."
      contentLabel="Lignes du tableau d’amortissement"
      textareaId="import-echeances"
      anchor="#import-echeances"
      causeId="loan-preview-causes"
      postCauseId="loan-post-causes"
      previewLabel="Prévisualiser les échéances"
      commitLabel="Comptabiliser les échéances"
      busy={false}
      action={(fn) => { void fn(); }}
      context={{ fiscal_year_id: 1, bank_account_id: 1, loan_id: 1 }}
      loanLabel="Crédit fictif"
      onImported={() => undefined}
    />,
    "/operations/emprunts",
    "/operations/:tab",
  );
  await userEvent.click(screen.getByText("Importer les échéances"));
  fireEvent.change(screen.getByLabelText("Lignes du tableau d’amortissement"), { target: { value: "Prêt;Date\n" } });
  await userEvent.click(screen.getByRole("button", { name: "Prévisualiser les échéances" }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Ligne 2, Total : La ventilation ne correspond pas au total.");
  expect(alert.compareDocumentPosition(screen.getByRole("table", { name: "Aperçu de l’import" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
