import { useRef, useState } from "react";
import {
  downloadImportTemplate,
  downloadRejects,
  type CsvCommitResult,
  type CsvField,
  type CsvPreview,
  type CsvProfile,
  type CsvInspect,
  type CsvRow,
} from "../api/csvImport";
import type { ApiErrorDetail } from "../api/errors";
import { operationsRequest } from "../api/operations";
import {
  csvPreviewCauses,
  describedBy,
  type ActionCause,
} from "./actionCauses";
import ApiErrorAlert from "./ApiErrorAlert";
import { BrowsableList } from "./BrowsableList";
import { EmptyState } from "./EmptyState";
import GlossaryTip from "./GlossaryTip";
import { GLOSSARY } from "./glossary";
import { SaveNoticeHost } from "./LocalFeedback";
import { useSaveNotice } from "./localFeedback";
import PrerequisiteList from "./PrerequisiteList";
import FrenchFileInput from "../lib/FrenchFileInput";
import { enumChoices, enumLabel, formatEuros, frenchCount, importPreviewSummary, importValidOnlyLabel } from "../lib/format";
import { ResponsiveTable } from "../lib/ResponsiveTable";
import FitSelect from "../lib/FitSelect";
import { contentHasPaidLines } from "./csvPaidLines";

const REJECT_FILE = {
  bank: "rejets-releve-bancaire.csv",
  operations: "rejets-recettes-depenses.csv",
  loan_payments: "rejets-echeances.csv",
} as const;

export default function CsvImportAssistant({
  profile,
  summaryTitle,
  intro,
  contentLabel,
  textareaId,
  anchor,
  causeId,
  postCauseId,
  previewLabel,
  commitLabel,
  busy,
  action,
  missingProperty = false,
  missingYear = false,
  missingBank = false,
  missingLoan = false,
  context,
  loanLabel,
  onImported,
}: {
  profile: CsvProfile;
  summaryTitle: string;
  intro: string;
  contentLabel: string;
  textareaId: string;
  anchor: string;
  causeId: string;
  postCauseId: string;
  previewLabel: string;
  commitLabel: string;
  busy: boolean;
  action: (fn: () => Promise<unknown>, step?: string) => void;
  missingProperty?: boolean;
  missingYear?: boolean;
  missingBank?: boolean;
  missingLoan?: boolean;
  context: {
    bank_account_id?: number | null;
    property_id?: number | null;
    fiscal_year_id?: number | null;
    loan_id?: number | null;
  };
  loanLabel?: string;
  onImported: () => void;
}) {
  const { notice, show, dismiss } = useSaveNotice();
  const place = `import-${textareaId}`;
  const [content, setContent] = useState("");
  const [headers, setHeaders] = useState<string[]>([]);
  const [fields, setFields] = useState<CsvField[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<CsvPreview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [acceptPartial, setAcceptPartial] = useState(false);
  const generation = useRef(0);
  const batchKey = useRef<string | null>(null);
  const paidWithoutBank = profile === "operations"
    && missingBank
    && contentHasPaidLines(content, mapping.paid);

  const causes = csvPreviewCauses({
    hasContent: content.trim() !== "",
    anchor,
    missingProperty,
    missingYear,
    missingBank: profile === "operations" ? false : missingBank,
    missingLoan,
    paidWithoutBank,
  });
  const postCauses = postRequirements(preview, profile, confirmed, anchor);
  const detail = preview && profile !== "operations" ? previewDetail(preview) : null;

  function updateContent(value: string) {
    const current = ++generation.current;
    setContent(value);
    setPreview(null);
    setConfirmed(false);
    setAcceptPartial(false);
    batchKey.current = null;
    if (!value.trim()) {
      setHeaders([]);
      setFields([]);
      setMapping({});
      return;
    }
    void operationsRequest<CsvInspect>("/imports/inspect", "POST", { content: value })
      .then((result) => {
        if (generation.current !== current || !result?.headers || !result.suggestions?.[profile]) return;
        setHeaders(result.headers);
        setFields(result.fields[profile] ?? []);
        setMapping(result.suggestions[profile] ?? {});
      })
      .catch(() => undefined);
  }

  function updateMapping(key: string, value: string) {
    generation.current += 1;
    setMapping((current) => ({ ...current, [key]: value }));
    setPreview(null);
    setConfirmed(false);
    setAcceptPartial(false);
    batchKey.current = null;
  }

  function body(confirmReference?: string) {
    return {
      content,
      mapping,
      bank_account_id: context.bank_account_id ?? null,
      property_id: context.property_id ?? null,
      fiscal_year_id: context.fiscal_year_id ?? null,
      loan_id: context.loan_id ?? null,
      ...(confirmReference ? { confirmed_loan_reference: confirmReference } : {}),
    };
  }

  function postImport(currentPreview: CsvPreview, partial: boolean) {
    const current = generation.current;
    const key = batchKey.current ?? crypto.randomUUID();
    batchKey.current = key;
    void action(async () => {
      const result = await operationsRequest<CsvCommitResult>(
        `/imports/${profile}/commit`,
        "POST",
        {
          ...body(currentPreview.loan_reference ?? undefined),
          ...(partial ? { import_valid_only: true } : {}),
        },
        profile === "operations" ? { headers: { "Idempotency-Key": key } } : undefined,
      );
      if (generation.current !== current) return;
      show({
        kind: GLOSSARY["import-csv"].label,
        name: IMPORT_NAMES[profile],
        action: "enregistré",
        targetId: place,
        detail: importedMessage(profile, result),
        next: IMPORT_NEXT[profile],
      });
      onImported();
      setPreview(null);
      setContent("");
      setHeaders([]);
      setMapping({});
      setConfirmed(false);
      setAcceptPartial(false);
      batchKey.current = null;
    }, "Comptabilisation de l’import…");
  }

  return (
    <details id={place} className="csv-import">
      <summary>{summaryTitle}</summary>
      <SaveNoticeHost place={place} notice={notice} onDismiss={dismiss} />
      <p>
        {intro}{" "}
        <GlossaryTip id="import-csv" />
      </p>
      <button type="button" disabled={busy} aria-busy={busy || undefined} onClick={() => {
        void action(() => downloadImportTemplate(profile), "Téléchargement du modèle…");
      }}>Télécharger le modèle CSV</button>
      <p className="form-help">
        UTF-8, séparateur point-virgule, décimales avec une virgule, dates JJ/MM/AAAA.
        Un fichier exporté avec une virgule ou collé depuis un tableur (tabulations) est lu aussi.
      </p>
      <FrenchFileInput
        label="Fichier CSV (1 Mo maximum)"
        accept=".csv,text/csv"
        disabled={busy}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (!file || busy) return;
          void action(async () => {
            if (file.size > 1_000_000) throw new Error("Fichier trop volumineux.");
            updateContent(await file.text());
          }, "Lecture du fichier…");
        }}
      />
      <label>{contentLabel}
        <textarea id={textareaId} rows={6} value={content} disabled={busy} onChange={(event) => updateContent(event.target.value)} />
      </label>
      {headers.length > 0 && fields.length > 0 && (
        <fieldset className="import-map">
          <legend>Associer les colonnes de votre fichier</legend>
          {fields.map((field) => (
            <label key={field.key}>
              {field.label}{field.required ? "" : " (facultatif)"}
              <FitSelect
                aria-label={field.label}
                value={mapping[field.key] ?? ""}
                onChange={(event) => updateMapping(field.key, event.target.value)}
              >
                <option value="">— Choisir —</option>
                {headers.map((header) => <option key={header} value={header}>{header}</option>)}
              </FitSelect>
            </label>
          ))}
        </fieldset>
      )}
      <button
        type="button"
        disabled={busy || causes.length > 0}
        aria-busy={busy || undefined}
        aria-describedby={describedBy(causeId, causes)}
        onClick={() => {
          const current = generation.current;
          void action(async () => {
            const result = await operationsRequest<CsvPreview>(
              `/imports/${profile}/preview`,
              "POST",
              body(),
            );
            if (generation.current !== current) return;
            setPreview(result);
            setHeaders(result.headers);
            setFields(result.fields);
            setMapping(result.mapping);
            setConfirmed(false);
            setAcceptPartial(false);
            batchKey.current ??= crypto.randomUUID();
          }, "Analyse du fichier…");
        }}
      >{previewLabel}</button>
      <PrerequisiteList id={causeId} causes={causes} />
      {detail && <ApiErrorAlert detail={detail} />}
      {preview && (
        <>
          {profile === "operations" ? (
            <OperationsPreview preview={preview} />
          ) : (
          <>
          <p>
            {preview.summary.count} ligne(s) : {preview.summary.valid} valide(s),{" "}
            {preview.summary.duplicate} doublon(s), {preview.summary.warning} avertissement(s),{" "}
            {preview.summary.error} erreur(s).
          </p>
          {preview.rows.length === 0 ? (
            <EmptyState
              title="Aucune ligne dans cet import."
              reason="Le fichier ne contient pas de ligne de données. Vérifiez l’en-tête et les lignes, puis relancez la prévisualisation."
              action={{ label: "Revenir au fichier", href: `#${textareaId}` }}
            />
          ) : (
            <BrowsableList
              items={preview.rows}
              searchLabel="Rechercher une ligne"
              text={(row) => `${row.line} ${Object.values(row.display).join(" ")} ${enumLabel("importStatus", row.status)}`}
              statusOf={(row) => row.status}
              statusChoices={enumChoices("importStatus")}
              emptyTitle="Aucune ligne dans cet import."
              emptyReason="Le fichier ne contient pas de ligne de données."
              noResultsReason="Aucune ligne ne correspond à la recherche ou au statut."
              groupBy={(row) => row.status}
              groupTitle={(key) => enumLabel("importStatus", key)}
            >
            {(rows) => (
            <ResponsiveTable
              label="Aperçu de l’import"
              caption="Aperçu de l’import"
              columns={[
                { key: "line", label: "Ligne" },
                { key: "status", label: "Statut" },
                ...preview.fields.map((field) => ({
                  key: field.key,
                  label: field.label,
                  priority: "secondary" as const,
                })),
                ...(profile === "bank" ? [{ key: "suggested", label: "Compte suggéré", priority: "secondary" as const }] : []),
                { key: "detail", label: "Détail" },
              ]}
              rows={rows.map((row) => ({
                key: String(row.line),
                className: `import-row-${row.status}`,
                cells: [
                  row.line,
                  enumLabel("importStatus", row.status),
                  ...preview.fields.map((field) => row.display[field.key] || "—"),
                  ...(profile === "bank" ? [row.suggested_account || "À choisir"] : []),
                  rowDetail(row),
                ],
              }))}
            />
            )}
            </BrowsableList>
          )}
          </>
          )}
          {preview.rejects_csv && (
            <button type="button" disabled={busy} onClick={() => downloadRejects(REJECT_FILE[profile], preview.rejects_csv)}>
              Télécharger les lignes à corriger
            </button>
          )}
          {profile === "loan_payments" && preview.loan_reference && preview.summary.importable > 0 && (
            <label id="confirmer-pret" tabIndex={-1}>
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              Je confirme que le prêt source {preview.loan_reference} correspond à {loanLabel}.
            </label>
          )}
          {profile === "operations" && preview.summary.error > 0 && preview.summary.importable > 0 && (
            <fieldset className="import-choice">
              <legend>Que faire des rejets ?</legend>
              <label>
                <input
                  type="radio"
                  name={`${textareaId}-decision`}
                  checked={!acceptPartial}
                  onChange={() => setAcceptPartial(false)}
                />
                <span>Corriger le fichier d’abord</span>
              </label>
              <label>
                <input
                  type="radio"
                  name={`${textareaId}-decision`}
                  checked={acceptPartial}
                  onChange={() => setAcceptPartial(true)}
                />
                <span>{importValidOnlyLabel(preview.summary.importable)}</span>
              </label>
            </fieldset>
          )}
          <button
            type="button"
            disabled={busy || postCauses.length > 0}
            aria-busy={busy || undefined}
            aria-describedby={describedBy(postCauseId, postCauses)}
            onClick={() => postImport(preview, false)}
          >{commitLabel}</button>
          <PrerequisiteList id={postCauseId} causes={postCauses} />
          {profile === "operations" && preview.summary.error > 0 && preview.summary.importable > 0 && (
            <button
              type="button"
              disabled={busy || !acceptPartial}
              aria-describedby={`${textareaId}-partial-note`}
              onClick={() => postImport(preview, true)}
            >{importValidOnlyLabel(preview.summary.importable)}</button>
          )}
          {profile === "operations" && preview.summary.error > 0 && preview.summary.importable > 0 && (
            <p id={`${textareaId}-partial-note`} className="form-help">
              Les lignes rejetées ne seront pas comptabilisées. Une écriture validée ne se modifie pas.
            </p>
          )}
        </>
      )}
    </details>
  );
}

function postRequirements(
  preview: CsvPreview | null,
  profile: CsvProfile,
  confirmed: boolean,
  anchor: string,
): ActionCause[] {
  if (!preview) return [];
  if (!preview.ready) {
    return [{
      code: "CSV_NOT_READY",
      message: "Associez les colonnes obligatoires avant de confirmer.",
      action: { label: "Revoir les colonnes", href: anchor },
    }];
  }
  if (profile === "operations" && preview.summary.error > 0) {
    return [{
      code: "CSV_REJECTS",
      message: preview.summary.importable > 0
        ? "Des lignes sont rejetées. Corrigez le fichier, ou confirmez l’import des seules lignes valides."
        : "Aucune ligne valide. Corrigez le fichier avant de comptabiliser.",
      action: { label: "Corriger le fichier", href: anchor },
    }];
  }
  if (preview.summary.importable === 0) {
    return [{
      code: "NOTHING_TO_IMPORT",
      message: "Aucune ligne nouvelle à importer.",
      action: { label: "Revoir l’aperçu", href: anchor },
    }];
  }
  if (profile === "loan_payments" && !confirmed) {
    return [{
      code: "LOAN_MAPPING",
      message: "Confirmez que le prêt du fichier est bien l’emprunt choisi.",
      action: { label: "Confirmer le prêt", href: `${anchor}#confirmer-pret` },
    }];
  }
  return [];
}

function previewDetail(preview: CsvPreview): ApiErrorDetail | null {
  const issues = [
    ...preview.issues,
    ...preview.rows.flatMap((row) => row.issues),
  ];
  if (!issues.length) return null;
  return {
    code: "CSV_INVALID",
    message: issues.length > 1
      ? `${issues.length} rejets. Les lignes valides peuvent être importées.`
      : "Un rejet est à corriger. Les lignes valides peuvent être importées.",
    location: "import",
    help: "import-csv",
    issues,
  };
}

function rowDetail(row: CsvPreview["rows"][number]): string {
  const item = row.issues[0] ?? row.warnings[0];
  if (!item) return "—";
  const value = item.value ? `Valeur « ${item.value} ». ` : item.value === "" ? "Valeur vide. " : "";
  const correction = item.correction ? `Correction : ${item.correction}` : "";
  return `${item.message} ${value}${correction}`.trim();
}

const IMPORT_NAMES = {
  bank: "relevé bancaire",
  operations: "recettes et dépenses",
  loan_payments: "échéancier",
} as const;

const IMPORT_NEXT = {
  bank: { label: "Rapprocher un mouvement", href: "/operations/banque" },
  operations: { label: "Vérifier le traitement fiscal", href: "/fiscalite#calcul-fiscal" },
  loan_payments: { label: "Rapprocher le relevé", href: "/operations/banque" },
} as const;

function importedMessage(profile: CsvProfile, result: CsvCommitResult): string {
  if (profile === "bank") {
    return `${frenchCount(result.imported, "mouvement importé", "mouvements importés")}, en attente de rapprochement.`;
  }
  if (profile === "operations") return operationsImportedMessage(result);
  return `${frenchCount(result.imported, "échéance comptabilisée", "échéances comptabilisées")}. Rapprochez ensuite le relevé bancaire.`;
}

function operationsImportedMessage(result: CsvCommitResult): string {
  const posted = result.batch?.posted_count ?? result.imported;
  const rejected = result.batch?.rejected_count ?? 0;
  const postedText = result.batch?.replayed
    ? `${frenchCount(posted, "ligne déjà comptabilisée", "lignes déjà comptabilisées")}. Aucun doublon.`
    : `${frenchCount(posted, "ligne comptabilisée", "lignes comptabilisées")}.`;
  const rejectedText = rejected === 0
    ? ""
    : rejected === 1
      ? " 1 ligne rejetée n’a pas été comptabilisée."
      : ` ${frenchCount(rejected, "ligne rejetée", "lignes rejetées")} n’ont pas été comptabilisées.`;
  return `${postedText}${rejectedText} Les lignes non payées restent à régler. Le traitement fiscal est à vérifier.`;
}

function OperationsPreview({ preview }: { preview: CsvPreview }) {
  const rejects = [...preview.issues, ...preview.rows.flatMap((row) => row.issues)];
  const ready = preview.rows.filter((row) => row.status !== "error");
  return (
    <>
      <p aria-live="polite">{importPreviewSummary(preview.summary)}</p>
      {rejects.length > 0 && (
        <ul className="import-rejects" aria-label="Lignes rejetées">
          {rejects.map((issue) => (
            <li key={`${issue.code}-${issue.line ?? "file"}-${issue.field ?? ""}-${issue.message}`}>
              {rejectSentence(issue)}
            </li>
          ))}
        </ul>
      )}
      {ready.length > 0 && (
        <ul className="import-ready" aria-label="Lignes prêtes">
          {ready.map((row) => (
            <li key={row.line}>{readyLine(row)}</li>
          ))}
        </ul>
      )}
    </>
  );
}

function rejectSentence(issue: CsvPreview["issues"][number]): string {
  const place = issue.line === undefined
    ? "Fichier"
    : issue.column
      ? `Ligne ${issue.line}, ${issue.column}`
      : `Ligne ${issue.line}`;
  const value = issue.value
    ? ` La valeur « ${issue.value} » est refusée.`
    : issue.value === ""
      ? " La valeur est vide."
      : "";
  const correction = issue.correction ? ` ${issue.correction}` : "";
  return `${place} : ${issue.message}${value}${correction}`;
}

function readyLine(row: CsvRow): string {
  const label = row.display.description || row.display.label || row.display.counterparty || "—";
  const amount = row.display.amount ? formatEuros(row.display.amount) : "";
  return [`Ligne ${row.line}`, label, amount, enumLabel("importStatus", row.status)].filter(Boolean).join(" · ");
}
