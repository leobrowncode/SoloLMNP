import { useRef, useState } from "react";
import {
  downloadImportTemplate,
  downloadRejects,
  type CsvField,
  type CsvPreview,
  type CsvProfile,
  type CsvInspect,
} from "../api/csvImport";
import type { ApiErrorDetail } from "../api/errors";
import { operationsRequest } from "../api/operations";
import {
  csvPreviewCauses,
  describedBy,
  type ActionCause,
} from "./actionCauses";
import ApiErrorAlert from "./ApiErrorAlert";
import GlossaryTip from "./GlossaryTip";
import PrerequisiteList from "./PrerequisiteList";
import FrenchFileInput from "../lib/FrenchFileInput";
import { enumLabel } from "../lib/format";

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
  onImported: (message: string) => void;
}) {
  const [content, setContent] = useState("");
  const [headers, setHeaders] = useState<string[]>([]);
  const [fields, setFields] = useState<CsvField[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<CsvPreview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const generation = useRef(0);

  const causes = csvPreviewCauses({
    hasContent: content.trim() !== "",
    anchor,
    missingProperty,
    missingYear,
    missingBank,
    missingLoan,
  });
  const postCauses = postRequirements(preview, profile, confirmed, anchor);
  const detail = preview ? previewDetail(preview) : null;

  function updateContent(value: string) {
    const current = ++generation.current;
    setContent(value);
    setPreview(null);
    setConfirmed(false);
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

  return (
    <details>
      <summary>{summaryTitle}</summary>
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
              <select
                aria-label={field.label}
                value={mapping[field.key] ?? ""}
                onChange={(event) => updateMapping(field.key, event.target.value)}
              >
                <option value="">— Choisir —</option>
                {headers.map((header) => <option key={header} value={header}>{header}</option>)}
              </select>
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
          }, "Analyse du fichier…");
        }}
      >{previewLabel}</button>
      <PrerequisiteList id={causeId} causes={causes} />
      {detail && <ApiErrorAlert detail={detail} />}
      {preview && (
        <>
          <p>
            {preview.summary.count} ligne(s) : {preview.summary.valid} valide(s),{" "}
            {preview.summary.duplicate} doublon(s), {preview.summary.warning} avertissement(s),{" "}
            {preview.summary.error} erreur(s).
          </p>
          {preview.rows.length > 0 && (
            <div className="ledger-table">
              <table>
                <caption>Aperçu de l’import</caption>
                <thead>
                  <tr>
                    <th>Ligne</th>
                    <th>Statut</th>
                    {preview.fields.map((field) => <th key={field.key}>{field.label}</th>)}
                    {profile === "bank" && <th>Compte suggéré</th>}
                    <th>Détail</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row) => (
                    <tr key={row.line} className={`import-row-${row.status}`}>
                      <td>{row.line}</td>
                      <td>{enumLabel("importStatus", row.status)}</td>
                      {preview.fields.map((field) => (
                        <td key={field.key}>{row.display[field.key] || "—"}</td>
                      ))}
                      {profile === "bank" && <td>{row.suggested_account || "À choisir"}</td>}
                      <td>{rowDetail(row)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
          <button
            type="button"
            disabled={busy || postCauses.length > 0}
            aria-busy={busy || undefined}
            aria-describedby={describedBy(postCauseId, postCauses)}
            onClick={() => {
              const current = generation.current;
              void action(async () => {
                const result = await operationsRequest<CsvPreview>(
                  `/imports/${profile}/commit`,
                  "POST",
                  body(preview.loan_reference ?? undefined),
                );
                if (generation.current !== current) return;
                onImported(importedMessage(profile, result.imported));
                setPreview(null);
                setContent("");
                setHeaders([]);
                setMapping({});
                setConfirmed(false);
              }, "Comptabilisation de l’import…");
            }}
          >{commitLabel}</button>
          <PrerequisiteList id={postCauseId} causes={postCauses} />
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

function importedMessage(profile: CsvProfile, imported: number): string {
  if (profile === "bank") {
    return `${imported} mouvement(s) importé(s), en attente de rapprochement.`;
  }
  if (profile === "operations") {
    return `${imported} opération(s) comptabilisée(s). Lignes non payées à régler ; traitement fiscal à vérifier.`;
  }
  return `${imported} échéance(s) comptabilisée(s). Rapprochez ensuite le relevé bancaire.`;
}
