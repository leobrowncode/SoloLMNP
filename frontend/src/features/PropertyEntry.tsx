import { useState } from "react";
import { assetsRequest as api } from "../api/assets";
import { operationsRequest, type Bank, type Loan, type Property } from "../api/operations";
import { useUnsavedGuard } from "../routing/useUnsavedGuard";
import {
  describedBy, propertyEntryPostCauses, propertyEntryPreviewCauses, propertyEntryStartCauses,
} from "./actionCauses";
import ApiErrorAlert from "./ApiErrorAlert";
import GlossaryTip from "./GlossaryTip";
import PrerequisiteList from "./PrerequisiteList";
import { idleView, toApiError, type ScreenView } from "./screenState";

interface YearOption { id: number; year: number; start_date?: string; status?: string }
interface EntryLine { account_number: string; label: string; debit: string; credit: string }
interface Preview {
  accounting_date: string;
  piece_date: string;
  lines: EntryLine[];
  owner_contribution: string;
  posted: boolean;
  entry_number?: string;
}

const CHARGES: [string, string, string][] = [
  ["interest", "661000", "Intérêts d’emprunt payés avant le début de l’exercice"],
  ["insurance", "616000", "Assurance emprunteur payée avant le début de l’exercice"],
  ["fees", "627000", "Frais de dossier et de garantie du prêt"],
];

function amount(value: string): string | null {
  const cleaned = value.replace(/\s/g, "").replace(",", ".");
  if (cleaned === "") return "0.00";
  return /^\d+(\.\d{1,2})?$/.test(cleaned) ? Number(cleaned).toFixed(2) : null;
}

export default function PropertyEntry({
  properties, years, onDone,
}: {
  properties: Property[];
  years: YearOption[];
  onDone: (message: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [banks, setBanks] = useState<Bank[]>([]);
  const [propertyId, setPropertyId] = useState(0);
  const [yearId, setYearId] = useState(0);
  const [outstanding, setOutstanding] = useState<Record<number, string>>({});
  const [bankId, setBankId] = useState(0);
  const [bankAmount, setBankAmount] = useState("");
  const [charges, setCharges] = useState<Record<string, string>>({});
  const [piece, setPiece] = useState("Acte d’acquisition");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [loadState, setLoadState] = useState<ScreenView<{ ready: true }>>(idleView());
  const [busy, setBusy] = useState(false);
  const entryDirty = open && (
    preview !== null
    || bankAmount.trim() !== ""
    || piece !== "Acte d’acquisition"
    || Object.values(charges).some((value) => value.trim() !== "")
    || Object.entries(outstanding).some(([id, value]) => {
      const loan = loans.find((row) => row.id === Number(id));
      return loan && value !== loan.initial_principal;
    })
  );
  useUnsavedGuard(entryDirty);

  async function start() {
    setError("");
    setLoadState({ phase: "loading", data: null, error: null, stale: false });
    try {
      const [loadedLoans, loadedBanks] = await Promise.all([
        operationsRequest<Loan[]>("/loans"), operationsRequest<Bank[]>("/banks"),
      ]);
      setLoans(loadedLoans);
      setBanks(loadedBanks);
      setOutstanding(Object.fromEntries(loadedLoans.map((row) => [row.id, row.initial_principal])));
      setPropertyId(properties[0]?.id ?? 0);
      setYearId(years[0]?.id ?? 0);
      setBankId(loadedBanks[0]?.id ?? 0);
      setLoadState({ phase: "loaded", data: { ready: true }, error: null, stale: false });
      setOpen(true);
    } catch (reason) {
      setLoadState({ phase: "error", data: null, error: toApiError(reason), stale: false });
    }
  }

  function payload(confirm: boolean) {
    const loanRows = loans
      .filter((row) => row.property_id === propertyId)
      .map((row) => ({ loan_id: row.id, outstanding: amount(outstanding[row.id] ?? "") }));
    const chargeRows = CHARGES.map(([key, account, label]) => ({
      account_number: account, label, amount: amount(charges[key] ?? ""),
    })).filter((row) => row.amount !== "0.00");
    const bank = amount(bankAmount);
    if ([...loanRows.map((row) => row.outstanding), ...chargeRows.map((row) => row.amount), bank].some((value) => value === null)) {
      return null;
    }
    return {
      fiscal_year_id: yearId,
      loans: loanRows,
      bank_account_id: bank !== "0.00" ? bankId : null,
      bank_amount: bank,
      prior_charges: chargeRows,
      piece_reference: piece.trim() || "Acte d’acquisition",
      confirm,
    };
  }

  async function submit(confirm: boolean) {
    setError("");
    const body = payload(confirm);
    if (!body) {
      setError("Montants attendus en euros, au centime près (ex. 14884,00).");
      return;
    }
    setBusy(true);
    try {
      const result = await api<Preview>(`/properties/${propertyId}/entry`, "POST", body);
      if (result.posted) {
        setOpen(false);
        setPreview(null);
        onDone(`Bien entré en comptabilité (écriture ${result.entry_number ?? ""}).`);
      } else {
        setPreview(result);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Écriture refusée.");
    } finally {
      setBusy(false);
    }
  }

  const openYears = years.filter((year) => year.status === undefined || year.status === "OPEN");
  const startCauses = propertyEntryStartCauses(properties.length, years);
  const startCauseId = "property-entry-causes";
  if (!open) {
    return <div className="property-entry">
      <button
        id="entree-bien"
        type="button"
        disabled={startCauses.length > 0}
        aria-describedby={describedBy(startCauseId, startCauses)}
        onClick={() => { void start(); }}
      >
        Faire entrer le bien en comptabilité
      </button>
      <PrerequisiteList id={startCauseId} causes={startCauses} />
      <p className="form-help">
        À faire une fois, après avoir créé les immobilisations du logement : inscrit au bilan le terrain, le bâtiment,
        les emprunts et les frais payés avant le début de l’exercice. L’écart va au compte de l’exploitant (108).
      </p>
      <div className="heading-with-help">
        <GlossaryTip id="compte-108" />
        <GlossaryTip id="extourne" />
      </div>
      {loadState.phase === "loading" && <p role="status">Chargement des emprunts et des comptes…</p>}
      {loadState.phase === "error" && loadState.error && (
        <ApiErrorAlert detail={loadState.error} onRetry={() => { void start(); }} />
      )}
      {error && <p role="alert" className="ledger-error">{error}</p>}
    </div>;
  }

  const propertyLoans = loans.filter((row) => row.property_id === propertyId);
  const previewCauses = propertyEntryPreviewCauses(propertyId, yearId);
  const postCauses = propertyEntryPostCauses(preview !== null);
  const previewCauseId = "property-entry-preview-causes";
  const postCauseId = "property-entry-post-causes";
  return <section className="review-form property-entry" aria-labelledby="property-entry-title">
    <h3 id="property-entry-title">Entrée du bien en comptabilité</h3>
    <p className="form-help">
      Une écriture unique, datée du premier jour de l’exercice. Les emprunts repris ici n’ont pas besoin
      de « déblocage » : saisissez ensuite seulement les échéances payées pendant l’exercice.
    </p>
    {error && <p role="alert" className="ledger-error">{error}</p>}
    <div className="form-grid">
      <label>Bien
        <select value={propertyId} onChange={(event) => { setPropertyId(Number(event.target.value)); setPreview(null); }}>
          {properties.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select>
      </label>
      <label>Exercice
        <select value={yearId} onChange={(event) => { setYearId(Number(event.target.value)); setPreview(null); }}>
          {openYears.map((row) => <option key={row.id} value={row.id}>{row.year}</option>)}
        </select>
      </label>
      {propertyLoans.map((row) => <label key={row.id} className="field-money">
        Capital restant dû au début de l’exercice — {row.lender} ({row.principal_account})
        <input inputMode="decimal" value={outstanding[row.id] ?? ""} onChange={(event) => {
          setOutstanding({ ...outstanding, [row.id]: event.target.value }); setPreview(null);
        }} />
      </label>)}
      <label>Compte bancaire
        <select value={bankId} onChange={(event) => { setBankId(Number(event.target.value)); setPreview(null); }}>
          {banks.map((row) => <option key={row.id} value={row.id}>{row.name} ({row.account_number})</option>)}
        </select>
      </label>
      <label className="field-money">Solde du compte bancaire au début de l’exercice (€)
        <input inputMode="decimal" value={bankAmount} placeholder="0,00" onChange={(event) => { setBankAmount(event.target.value); setPreview(null); }} />
      </label>
      {CHARGES.map(([key, account, label]) => <label key={key} className="field-money">
        {label} ({account})
        <input inputMode="decimal" value={charges[key] ?? ""} placeholder="0,00" onChange={(event) => {
          setCharges({ ...charges, [key]: event.target.value }); setPreview(null);
        }} />
      </label>)}
      <label>Référence de la pièce
        <input value={piece} onChange={(event) => setPiece(event.target.value)} />
      </label>
    </div>
    <div className="form-actions">
      <button id="property-entry-preview" type="button" disabled={busy || previewCauses.length > 0} aria-describedby={describedBy(previewCauseId, previewCauses)} onClick={() => { void submit(false); }}>Prévisualiser l’écriture</button>
      <PrerequisiteList id={previewCauseId} causes={previewCauses} />
      <button type="button" disabled={busy || postCauses.length > 0} aria-describedby={describedBy(postCauseId, postCauses)} onClick={() => { void submit(true); }}>Comptabiliser</button>
      <PrerequisiteList id={postCauseId} causes={postCauses} />
      <button type="button" onClick={() => { setOpen(false); setPreview(null); }}>Annuler</button>
    </div>
    {preview?.owner_contribution.startsWith("-") && <p className="field-hint">
      Les emprunts dépassent le terrain, le bâtiment et les frais repris : le solde passe en prélèvement
      de l’exploitant. Si cet argent était encore sur votre compte au début de l’exercice, indiquez ce solde bancaire.
    </p>}
    {preview && <div className="ledger-table">
      <table>
        <caption>
          Écriture du {preview.accounting_date} (pièce du {preview.piece_date}) ·{" "}
          {preview.owner_contribution.startsWith("-")
            ? `prélèvement de l’exploitant ${preview.owner_contribution.slice(1)} €`
            : `apport de l’exploitant ${preview.owner_contribution} €`}
        </caption>
        <thead><tr><th>Compte</th><th>Libellé</th><th>Débit (€)</th><th>Crédit (€)</th></tr></thead>
        <tbody>
          {preview.lines.map((line, index) => <tr key={`${line.account_number}-${index}`}>
            <td>{line.account_number}</td><td>{line.label}</td><td>{line.debit}</td><td>{line.credit}</td>
          </tr>)}
        </tbody>
      </table>
    </div>}
  </section>;
}
