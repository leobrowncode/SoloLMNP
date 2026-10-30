import { outputLabel, outputTrust, readyToCopy } from "./outputStatus";
import GlossaryTip from "./GlossaryTip";

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
interface PersonalLine { case: string; case_declarant_2: string; label: string; amount: string }
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
    lines?: PersonalLine[];
    prior_deficits?: { origin_year: number; case: string | null; amount: string }[];
    note?: string;
  };
}

const LEVEL_LABELS: Record<string, string> = {
  info: "Information",
  warning: "Avertissement",
  error: "Erreur",
};

function levelLabel(level?: string): string {
  if (!level) return "Avertissement";
  return LEVEL_LABELS[level] ?? level;
}

const FORMS: [string, string][] = [
  ["2031-SD", "2031 — déclaration de résultat"],
  ["2031-BIS-SD", "2031-bis — BIC non professionnels"],
  ["2033-A-SD", "2033-A — bilan simplifié"],
  ["2033-B-SD", "2033-B — compte de résultat et résultat fiscal"],
  ["2033-C-SD", "2033-C — immobilisations et amortissements"],
  ["2033-E-SD", "2033-E — valeur ajoutée"],
];

function frDate(value?: string): string {
  if (!value) return "—";
  const [y, m, d] = value.split("-");
  return `${d}/${m}/${y}`;
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

      {FORMS.map(([form, title]) => {
        const rows = fields.filter((field) => (field.form_ref ?? worksheet.liasse?.form) === form);
        if (rows.length === 0) return null;
        return (
          <div className="ledger-table" key={form}>
            <table>
              <caption>{title}</caption>
              <thead><tr><th>Case</th><th>Libellé</th><th>Montant (€)</th></tr></thead>
              <tbody>
                {rows.map((field) => (
                  <tr key={field.code}>
                    <td>{field.official_case ?? "—"}</td>
                    <td>{field.label}</td>
                    <td>{field.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}

      {tracking && (
        <div className="ledger-table">
          <table>
            <caption>État de suivi des amortissements non déduits (art. 39 C) — à conserver avec la liasse</caption>
            <tbody>
              <tr><td>Dotation comptable de l’exercice</td><td>{tracking.accounting_depreciation} €</td></tr>
              <tr><td>Plafond (loyers − autres charges)</td><td>{tracking.capacity} €</td></tr>
              <tr><td>Dotation déduite cette année</td><td>{tracking.deducted_current} €</td></tr>
              <tr><td>Non déduite, réintégrée ligne 318</td><td>{tracking.deferred_current} €</td></tr>
              <tr><td>Reprise d’années antérieures, déduite ligne 350</td><td>{tracking.prior_used} €</td></tr>
              {tracking.prior.map((row) => (
                <tr key={row.origin_year}>
                  <td>Stock {row.origin_year} : {row.opening} €, repris {row.used} €</td>
                  <td>reste {row.remaining} €</td>
                </tr>
              ))}
              <tr><td><strong>Stock total reporté</strong></td><td><strong>{tracking.remaining_total} €</strong></td></tr>
            </tbody>
          </table>
        </div>
      )}

      {(personal.lines ?? []).length > 0 && (
        <div className="ledger-table">
          <table>
            <caption>2042-C-PRO — déclaration de revenus du foyer (à part de la liasse)</caption>
            <thead><tr><th>Case</th><th>Libellé</th><th>Montant (€)</th></tr></thead>
            <tbody>
              {personal.lines?.map((line) => (
                <tr key={line.case}>
                  <td>{line.case} <span className="field-hint">(déclarant 2 : {line.case_declarant_2})</span></td>
                  <td>{line.label}</td>
                  <td>{line.amount}</td>
                </tr>
              ))}
              {personal.prior_deficits?.map((row) => (
                <tr key={row.origin_year}>
                  <td>{row.case ?? "à vérifier"}</td>
                  <td>Déficit LMNP {row.origin_year} non encore imputé</td>
                  <td>{row.amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {personal.note && <p className="field-hint">{personal.note}</p>}
        </div>
      )}

      {(worksheet.by_property ?? []).length > 1 && (
        <div className="ledger-table">
          <table>
            <caption>Répartition par bien (information)</caption>
            <thead><tr><th>Bien</th><th>Loyers (€)</th><th>Charges (€)</th><th>Dotations (€)</th></tr></thead>
            <tbody>
              {worksheet.by_property?.map((row) => (
                <tr key={row.property_id}>
                  <td>{row.name}</td><td>{row.rents}</td><td>{row.expenses}</td><td>{row.depreciation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="field-hint">
        {ready
          ? "SoloLMNP n’envoie rien. Recopiez ces montants dans votre espace professionnel, validez la déclaration, puis conservez l’accusé de dépôt avec le dossier de contrôle."
          : "SoloLMNP n’envoie rien. Ces montants ne sont pas une base de déclaration : ne les recopiez pas."}
      </p>
    </div>
  );
}
