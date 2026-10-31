import { outputLabel, outputTrust, readyToCopy } from "./outputStatus";
import GlossaryTip from "./GlossaryTip";
import { idleCaseSentence, visiblePersonalLines } from "./personalCases";
import { enumLabel, formatAmount, formatEuros, formatIsoDate } from "../lib/format";
import { ResponsiveTable } from "../lib/ResponsiveTable";

interface Field {
  code: string;
  form_ref?: string;
  official_case: string | null;
  label: string;
  value: string;
  expression: string;
  rules?: string[];
  accounts?: string[];
  entries?: number[];
}
interface PropertySegment {
  property_id: number;
  name: string;
  rents: string;
  expenses: string;
  depreciation: string;
}
interface Notice { code: string; message: string; level?: string }
interface PersonalLine {
  code?: string;
  case: string | null;
  case_declarant_2?: string | null;
  case_status?: string;
  served?: boolean;
  label: string;
  amount: string;
  source_url?: string | null;
  block_reason?: string | null;
}
interface RuleRef { id: string | null; source?: string | null; source_url?: string | null }
interface EntryBrief {
  id: number;
  accounting_date: string;
  journal_code: string;
  piece_reference: string;
  label: string;
  accounts: string[];
}
interface Explanation {
  code: string;
  label: string;
  amount: string | null;
  formula: string;
  rules: RuleRef[];
  entries: EntryBrief[];
}
interface EfiRow {
  code: string;
  form: string;
  case: string | null;
  case_status: string;
  block_reason?: string | null;
  label: string;
  amount: string | null;
  formula: string;
  rules: RuleRef[];
  source_label?: string | null;
  source_url?: string | null;
  entries?: EntryBrief[];
}
interface BlockedCase { case: string; reason: string }
interface UsageRow {
  origin_year: number;
  opening: string;
  used: string;
  remaining_after: string;
  case: string | null;
  case_status: string;
}
export interface Declaration {
  marker: string;
  status: string;
  vintage: string;
  rules_version?: string | null;
  explanations: Explanation[];
  efi_rows: EfiRow[];
}
interface Tracking {
  accounting_depreciation: string;
  capacity: string;
  deducted_current: string;
  deferred_current: string;
  prior_used: string;
  prior: { origin_year: number; opening: string; used: string; remaining: string }[];
  remaining_total: string;
}
export interface Worksheet {
  year?: number;
  transmission: boolean;
  declarable?: boolean;
  output_status?: string;
  output_label?: string;
  copy_complete?: boolean;
  frozen?: boolean;
  disclaimer: string;
  portal?: string;
  vintage_note?: string;
  declarant?: { name: string; siren: string | null; siret: string | null };
  exercise?: { start: string; end: string };
  instructions?: string[];
  blocking?: Notice[];
  warnings?: Notice[];
  depreciation_tracking?: Tracking | null;
  by_property?: PropertySegment[];
  liasse?: { form: string; vintage: string; fields: Field[] };
  personal_return: {
    form: string;
    status: string;
    cerfa?: string | null;
    form_millesime?: string | null;
    lines?: PersonalLine[];
    prior_deficits?: {
      origin_year: number;
      case: string | null;
      case_status?: string;
      amount: string;
      block_reason?: string | null;
    }[];
    deficit_usage?: UsageRow[];
    blocked_cases?: BlockedCase[];
    unfilled_cases?: BlockedCase[];
    source?: { title?: string | null; pdf_url?: string | null; page_url?: string | null } | null;
    note?: string;
  };
  declaration?: Declaration;
}

function levelLabel(level?: string): string {
  if (!level) return enumLabel("worksheetLevel", "warning");
  return enumLabel("worksheetLevel", level);
}

const FORMS: [string, string][] = [
  ["2031-SD", "2031 — déclaration de résultat"],
  ["2031-BIS-SD", "2031-bis — BIC non professionnels"],
  ["2033-A-SD", "2033-A — bilan simplifié"],
  ["2033-B-SD", "2033-B — compte de résultat et résultat fiscal"],
  ["2033-C-SD", "2033-C — immobilisations et amortissements"],
  ["2033-E-SD", "2033-E — valeur ajoutée"],
];

function shownAmount(value: string | null | undefined): string {
  if (!value) return "—";
  return formatAmount(value);
}

function caseText(status: string | undefined, official: string | null | undefined): string {
  if (status === "verified" && official) return official;
  if (status === "unnumbered") return "non numérotée";
  if (!status && official) return official;
  return "bloquée";
}

function RuleLinks({ rules }: { rules: RuleRef[] }) {
  if (rules.length === 0) return null;
  return (
    <ul className="field-hint">
      {rules.map((rule, index) => (
        <li key={`${rule.id ?? rule.source_url ?? "regle"}-${index}`}>
          {rule.source_url ? (
            <a href={rule.source_url} target="_blank" rel="noreferrer">
              {rule.id ?? "source officielle"}
            </a>
          ) : (
            <span>{rule.id ?? "règle"}</span>
          )}
          {rule.source ? ` — ${rule.source}` : ""}
        </li>
      ))}
    </ul>
  );
}

function uniqueEntries(entries: EntryBrief[]): EntryBrief[] {
  const seen = new Set<number>();
  const rows: EntryBrief[] = [];
  for (const entry of entries) {
    if (seen.has(entry.id)) continue;
    seen.add(entry.id);
    rows.push(entry);
  }
  return rows;
}

function EntryList({ entries }: { entries: EntryBrief[] }) {
  const rows = uniqueEntries(entries);
  if (rows.length === 0) return <p className="field-hint">Aucune écriture de ledger sur cette ligne.</p>;
  return (
    <details>
      <summary>{rows.length} écriture{rows.length > 1 ? "s" : ""} source</summary>
      <ul>
        {rows.map((entry) => (
          <li key={entry.id}>
            {frDate(entry.accounting_date)} · {entry.journal_code} · {entry.piece_reference || "sans pièce"} · {entry.label}
            {entry.accounts.length > 0 ? ` · ${entry.accounts.join(", ")}` : ""}
          </li>
        ))}
      </ul>
    </details>
  );
}

function DeclarationPanel({
  declaration,
  personal,
}: {
  declaration: Declaration;
  personal: Worksheet["personal_return"];
}) {
  const usage = personal.deficit_usage ?? [];
  const personalView = visiblePersonalLines(personal.lines ?? []);
  return (
    <section id="declaration" aria-label="Déclaration">
      <h3>Déclaration</h3>
      <p className="fiscal-goal fiscal-goal-recherche" data-declaration-status={declaration.status}>
        <strong>{declaration.marker}</strong>
        {` — millésime ${declaration.vintage}`}
        {declaration.rules_version ? ` · règles ${declaration.rules_version}` : " · version de règles non rapprochée du calcul"}
        . Cette feuille reste en recherche.
      </p>
      <p>
        Saisie et envoi manuels uniquement. Pas de scraping, pas d’EDI, pas de télétransmission.
      </p>

      <h3>Calculs</h3>
      {declaration.explanations.map((item, index) => (
        <details key={`${item.code}-${index}`}>
          <summary>{item.label} — {shownAmount(item.amount)} €</summary>
          <p>Formule : {item.formula}</p>
          <RuleLinks rules={item.rules} />
          <EntryList entries={item.entries} />
        </details>
      ))}

      <ResponsiveTable
        label="Feuille EFI"
        caption="EFI — liasse à recopier (2031 et 2033)"
        columns={[
          { key: "form", label: "Formulaire" },
          { key: "case", label: "Case" },
          { key: "label", label: "Libellé" },
          { key: "amount", label: "Montant (€)" },
          { key: "formula", label: "Formule", priority: "secondary" },
        ]}
        rows={declaration.efi_rows.map((row, index) => ({
          key: `${row.form}-${row.code}-${index}`,
          cells: [
            row.form,
            caseText(row.case_status, row.case),
            <>
              {row.label}
              {row.block_reason && <p className="field-hint">{row.block_reason} Ne pas recopier.</p>}
              {row.source_url && (
                <p className="field-hint">
                  <a href={row.source_url} target="_blank" rel="noreferrer">
                    {row.source_label ?? "Source officielle"}
                  </a>
                </p>
              )}
              <EntryList entries={row.entries ?? []} />
            </>,
            shownAmount(row.amount),
            row.formula,
          ],
        }))}
      />

      <h3>2042-C-PRO</h3>
      <p className="field-hint">
        Déclaration de revenus du foyer, à part de la liasse.
        {personal.cerfa ? ` CERFA ${personal.cerfa}` : ""}
        {personal.form_millesime ? `, formulaire ${personal.form_millesime}` : ""}
        {personal.status === "case_not_verified" ? ". Cases non publiées pour ce millésime." : "."}
      </p>
      {personal.source?.pdf_url && (
        <p className="liasse-links">
          <a href={personal.source.pdf_url} target="_blank" rel="noreferrer">
            {personal.source.title ?? "Formulaire 2042-C-PRO"}
          </a>
        </p>
      )}
      <ResponsiveTable
        label="2042-C-PRO"
        caption="2042-C-PRO — résultat BIC non professionnel"
        columns={[
          { key: "case", label: "Case" },
          { key: "label", label: "Libellé" },
          { key: "amount", label: "Montant (€)" },
        ]}
        rows={personalView.shown.map((line, index) => ({
          key: `${line.code ?? line.case ?? line.label}-${index}`,
          cells: [
            caseText(line.case_status, line.case),
            <>
              {line.label}
              {line.block_reason && <p className="field-hint">{line.block_reason}</p>}
            </>,
            shownAmount(line.amount),
          ],
        }))}
      />
      {usage.length > 0 && (
        <ResponsiveTable
          label="Reports de déficits"
          caption="Registre des déficits LMNP — usage du report"
          columns={[
            { key: "year", label: "Origine" },
            { key: "case", label: "Case" },
            { key: "opening", label: "Avant imputation (€)" },
            { key: "used", label: "Imputé (€)", priority: "secondary" },
            { key: "after", label: "Reste (€)", priority: "secondary" },
          ]}
          rows={usage.map((row) => ({
            key: String(row.origin_year),
            cells: [
              String(row.origin_year),
              caseText(row.case_status, row.case),
              shownAmount(row.opening),
              shownAmount(row.used),
              shownAmount(row.remaining_after),
            ],
          }))}
        />
      )}
      {(personal.prior_deficits ?? []).length > 0 && usage.length === 0 && (
        <ul>
          {personal.prior_deficits?.map((row) => (
            <li key={row.origin_year}>
              Déficit LMNP {row.origin_year} : {caseText(row.case_status, row.case)} — {shownAmount(row.amount)} €
              {row.block_reason ? `. ${row.block_reason}` : ""}
            </li>
          ))}
        </ul>
      )}
      {(personal.blocked_cases ?? []).length > 0 && (
        <ul aria-label="Cases 2042 bloquées">
          {personal.blocked_cases?.map((item) => (
            <li key={item.case}>Ne pas utiliser la case {item.case}. {item.reason}</li>
          ))}
        </ul>
      )}
      {(personal.unfilled_cases ?? []).length > 0 && (
        <ul aria-label="Cases 2042 non remplies">
          {personal.unfilled_cases?.map((item) => (
            <li key={item.case}>Case {item.case} non remplie. {item.reason}</li>
          ))}
        </ul>
      )}
      {personalView.idleCase
        ? <p className="field-hint">{idleCaseSentence(personalView.idleCase)}</p>
        : personal.note && <p className="field-hint">{personal.note}</p>}
    </section>
  );
}

function frDate(value?: string): string {
  if (!value) return "—";
  const shown = formatIsoDate(value);
  return shown === value.trim() ? value : shown;
}

export default function LiasseSheet({ worksheet }: { worksheet: Worksheet }) {
  const fields = worksheet.liasse?.fields ?? [];
  const blocking = worksheet.blocking ?? [];
  const warnings = worksheet.warnings ?? [];
  const tracking = worksheet.depreciation_tracking;
  const personal = worksheet.personal_return;
  const trust = outputTrust(worksheet);
  const ready = readyToCopy(worksheet);
  const tone = trust === "declarable" ? "good" : trust === "provisoire" ? "warn" : "recherche";
  return (
    <div className="fiscal-panel liasse-sheet" aria-live="polite">
      <div className="heading-with-help">
        <h3>Liasse à recopier</h3>
        <GlossaryTip id="liasse" />
        <GlossaryTip id="efi" />
        <GlossaryTip id="declaration-foyer" />
        <GlossaryTip id="report-amortissement" />
      </div>
      <p className={`fiscal-goal fiscal-goal-${tone}`} data-output-status={trust}>
        <strong>
          {ready ? `${outputLabel(worksheet)} — Prête à recopier` : outputLabel(worksheet)}
        </strong>
        {" — "}{worksheet.disclaimer}
      </p>
      <p>
        Exercice du {frDate(worksheet.exercise?.start)} au {frDate(worksheet.exercise?.end)}
        {worksheet.declarant ? ` · ${worksheet.declarant.name}` : ""}
        {` · SIREN ${worksheet.declarant?.siren ?? "à renseigner"}`}
        {worksheet.declarant?.siret ? ` · SIRET ${worksheet.declarant.siret}` : ""}
        {" · "}
        {worksheet.frozen ? "montants figés à la clôture" : "calcul en cours : clôturez pour figer"}
      </p>
      {worksheet.vintage_note && <p className="field-hint">{worksheet.vintage_note}</p>}

      {blocking.length > 0 && (
        <div className="ledger-error" role="alert">
          <p><strong>À corriger avant de déclarer</strong></p>
          <ul>{blocking.map((item) => <li key={item.code + item.message}>{item.message}</li>)}</ul>
        </div>
      )}

      {warnings.length > 0 && (
        <ul className="worksheet-warnings" aria-label="Avertissements de la liasse">
          {warnings.map((item) => (
            <li
              key={item.code + item.level + item.message}
              className={`worksheet-warning worksheet-warning-${item.level ?? "warning"}`}
            >
              <strong>{levelLabel(item.level)}</strong>
              <span>{item.message}</span>
            </li>
          ))}
        </ul>
      )}

      <p className="liasse-links">
        <a href={worksheet.portal ?? "https://www.impots.gouv.fr/professionnel/teleprocedures-efi-ou-edi"} target="_blank" rel="noreferrer">
          impots.gouv.fr — déclarer en mode EFI
        </a>
      </p>
      <p className="field-hint">
        Le PDF, le FEC et le dossier de contrôle sont au-dessus. Chacun est marqué Provisoire, Bloquée ou Finale. Un téléchargement refusé reste sur cette page.
      </p>

      {(worksheet.instructions ?? []).length > 0 && (
        <details open>
          <summary>Consignes de saisie</summary>
          <ol>{worksheet.instructions?.map((item) => <li key={item}>{item}</li>)}</ol>
        </details>
      )}

      {worksheet.declaration ? (
        <DeclarationPanel declaration={worksheet.declaration} personal={personal} />
      ) : FORMS.map(([form, title]) => {
        const rows = fields.filter((field) => (field.form_ref ?? worksheet.liasse?.form) === form);
        if (rows.length === 0) return null;
        return (
          <ResponsiveTable
            key={form}
            label={title}
            caption={title}
            columns={[
              { key: "case", label: "Case" },
              { key: "amount", label: "Montant (€)" },
              { key: "label", label: "Libellé", priority: "secondary" },
            ]}
            rows={rows.map((field, index) => ({
              key: `${form}-${field.code}-${index}`,
              cells: [field.official_case ?? "—", formatAmount(field.value), field.label],
            }))}
          />
        );
      })}

      {tracking && (
        <ResponsiveTable
          label="Suivi des amortissements"
          caption="État de suivi des amortissements non déduits (art. 39 C) — à conserver avec la liasse"
          columns={[
            { key: "label", label: "Élément" },
            { key: "amount", label: "Montant" },
          ]}
          rows={[
            { key: "accounting", cells: ["Dotation comptable de l’exercice", formatEuros(tracking.accounting_depreciation)] },
            { key: "capacity", cells: ["Plafond (loyers − autres charges)", formatEuros(tracking.capacity)] },
            { key: "deducted", cells: ["Dotation déduite cette année", formatEuros(tracking.deducted_current)] },
            { key: "deferred", cells: ["Non déduite, réintégrée ligne 318", formatEuros(tracking.deferred_current)] },
            { key: "prior-used", cells: ["Reprise d’années antérieures, déduite ligne 350", formatEuros(tracking.prior_used)] },
            ...tracking.prior.map((row) => ({
              key: `prior-${row.origin_year}`,
              cells: [
                `Stock ${row.origin_year} : ${formatEuros(row.opening)}, repris ${formatEuros(row.used)}`,
                `reste ${formatEuros(row.remaining)}`,
              ],
            })),
            { key: "total", cells: ["Stock total reporté", formatEuros(tracking.remaining_total)] },
          ]}
        />
      )}

      {!worksheet.declaration && (personal.lines ?? []).length > 0 && (() => {
        const personalView = visiblePersonalLines(personal.lines ?? []);
        return (
          <>
            <ResponsiveTable
              label="2042-C-PRO"
              caption="2042-C-PRO — déclaration de revenus du foyer (à part de la liasse)"
              columns={[
                { key: "case", label: "Case" },
                { key: "amount", label: "Montant (€)" },
                { key: "label", label: "Libellé", priority: "secondary" },
              ]}
              rows={[
                ...personalView.shown.map((line, index) => ({
                  key: `${line.case ?? "case"}-${index}`,
                  cells: [line.case ?? "—", formatAmount(line.amount), line.label],
                })),
                ...(personal.prior_deficits ?? []).map((row) => ({
                  key: `deficit-${row.origin_year}`,
                  cells: [
                    row.case ?? "à vérifier",
                    formatAmount(row.amount),
                    `Déficit LMNP ${row.origin_year} non encore imputé`,
                  ],
                })),
              ]}
            />
            {personalView.idleCase
              ? <p className="field-hint">{idleCaseSentence(personalView.idleCase)}</p>
              : personal.note && <p className="field-hint">{personal.note}</p>}
          </>
        );
      })()}

      {(worksheet.by_property ?? []).length > 1 && (
        <ResponsiveTable
          label="Répartition par bien"
          caption="Répartition par bien (information)"
          columns={[
            { key: "name", label: "Bien" },
            { key: "rents", label: "Loyers (€)" },
            { key: "expenses", label: "Charges (€)", priority: "secondary" },
            { key: "depreciation", label: "Dotations (€)", priority: "secondary" },
          ]}
          rows={worksheet.by_property?.map((row) => ({
            key: String(row.property_id),
            cells: [row.name, formatAmount(row.rents), formatAmount(row.expenses), formatAmount(row.depreciation)],
          })) ?? []}
        />
      )}
      <p className="field-hint">
        {ready
          ? "SoloLMNP n’envoie rien. Recopiez ces montants dans votre espace professionnel, validez la déclaration, puis conservez l’accusé de dépôt avec le dossier de contrôle."
          : "SoloLMNP n’envoie rien. Ces montants ne sont pas une base de déclaration : ne les recopiez pas."}
      </p>
    </div>
  );
}
