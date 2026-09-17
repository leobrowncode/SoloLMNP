import { useEffect, useState } from "react";
import { request, type Setup } from "../api/ledger";
import "./ledger.css";

interface Row { account_number: string; label: string; amount: string }
export interface Statements {
  fiscal_year_id: number; start_date: string; end_date: string; excluded_draft_count: number;
  income_statement: { income: Row[]; expenses: Row[]; total_income: string; total_expenses: string; result: string };
  balance_sheet: { assets: Row[]; liabilities: Row[]; equity: Row[]; total_assets: string; total_liabilities: string; total_equity: string; current_result: string; total_liabilities_and_equity: string };
}

function Accounts({ title, rows, total }: { title: string; rows: Row[]; total: string }) {
  return <section><h4>{title}</h4><table><caption>{title} par compte</caption>
    <thead><tr><th>Compte</th><th>Libellé</th><th>Solde (€)</th></tr></thead>
    <tbody>{rows.map((row) => <tr key={row.account_number}><td>{row.account_number}</td><td>{row.label}</td><td>{row.amount}</td></tr>)}</tbody>
    <tfoot><tr><th colSpan={2}>Total {title.toLowerCase()}</th><td>{total}</td></tr></tfoot>
  </table></section>;
}

export default function StatementsPage() {
  const [setup, setSetup] = useState<Setup | null>(null);
  const [year, setYear] = useState(0);
  const [data, setData] = useState<Statements | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let current = true;
    void request<Setup>("/setup").then((value) => {
      if (current) { setSetup(value); setYear(value.years[0]?.id ?? 0); }
    }, (reason: Error) => { if (current) setError(reason.message); });
    return () => { current = false; };
  }, []);
  useEffect(() => {
    if (!year) return;
    let current = true;
    void request<Statements>(`/years/${year}/statements`).then((value) => {
      if (current) setData(value);
    }, (reason: Error) => { if (current) setError(reason.message); });
    return () => { current = false; };
  }, [year, attempt]);
  function refresh(nextYear = year) {
    setData(null); setError(""); setYear(nextYear); setAttempt((value) => value + 1);
  }
  return <section className="ledger-page" aria-labelledby="statements-title">
    <h2 id="statements-title">États comptables provisoires</h2>
    <p>Calculés uniquement sur les écritures validées. Inventaire et continuité entre exercices restent à contrôler. Aucun montant déclarable.</p>
    {setup && setup.years.length === 0 && <p>Créez un exercice dans Comptabilité pour consulter ses états.</p>}
    {setup && setup.years.length > 0 && <div className="toolbar">
      <label>Exercice <select value={year} onChange={(event) => refresh(Number(event.target.value))}>{setup.years.map((item) => <option key={item.id} value={item.id}>{item.year}</option>)}</select></label>
      <button type="button" onClick={() => refresh()}>Actualiser les états</button>
    </div>}
    {error && <p role="alert">{error}</p>}
    {!error && (!setup || (year !== 0 && !data)) && <p role="status">Chargement des états…</p>}
    {data && <div aria-live="polite">
      <p>Période : {data.start_date} — {data.end_date}. Brouillons exclus : {data.excluded_draft_count}.</p>
      <h3>Compte de résultat</h3>
      <Accounts title="Produits" rows={data.income_statement.income} total={data.income_statement.total_income} />
      <Accounts title="Charges" rows={data.income_statement.expenses} total={data.income_statement.total_expenses} />
      <p><strong>Résultat comptable : {data.income_statement.result} €</strong></p>
      <h3>Bilan par compte</h3>
      <p>Soldes signés selon le classement du plan de comptes. Les amortissements diminuent l’actif. La présentation réglementaire et les reclassements restent à établir.</p>
      <Accounts title="Actif net" rows={data.balance_sheet.assets} total={data.balance_sheet.total_assets} />
      <Accounts title="Dettes" rows={data.balance_sheet.liabilities} total={data.balance_sheet.total_liabilities} />
      <Accounts title="Capitaux propres hors résultat" rows={data.balance_sheet.equity} total={data.balance_sheet.total_equity} />
      <p>Résultat de l’exercice : {data.balance_sheet.current_result} €</p>
      <p><strong>Total passif et capitaux propres : {data.balance_sheet.total_liabilities_and_equity} €</strong></p>
    </div>}
  </section>;
}
