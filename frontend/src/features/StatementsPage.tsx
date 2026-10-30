import { useEffect, useState } from "react";
import { downloadFiling } from "../api/download";
import { RequestError, request, type Setup } from "../api/ledger";
import ApiErrorAlert from "./ApiErrorAlert";
import OpeningPreview from "./OpeningPreview";
import ResultClosing from "./ResultClosing";
import ScreenStatus from "./ScreenStatus";
import GlossaryTip from "./GlossaryTip";
import {
  beginLoad, defer, failLoad, finishLoad, idleView, showsData, toApiError, type ScreenView,
} from "./screenState";
import "./ledger.css";

interface Row { account_number: string; label: string; amount: string }
interface Rubric { code: string; label: string; accounts: Row[]; total: string }
export interface Statements {
  fiscal_year_id: number; start_date: string; end_date: string; excluded_draft_count: number;
  income_statement: { income: Row[]; expenses: Row[]; total_income: string; total_expenses: string; result: string };
  balance_sheet: { assets: Row[]; liabilities: Row[]; equity: Row[]; total_assets: string; total_liabilities: string; total_equity: string; current_result: string; total_liabilities_and_equity: string };
  presentation?: { reclassifications_applied: boolean; balance_rubrics: Rubric[]; income_rubrics: Rubric[]; warnings: { code: string; message: string }[] };
}

function Accounts({ title, rows, total }: { title: string; rows: Row[]; total: string }) {
  return <section><h4>{title}</h4><table><caption>{title} par compte</caption>
    <thead><tr><th>Compte</th><th>Libellé</th><th>Solde (€)</th></tr></thead>
    <tbody>{rows.map((row) => <tr key={row.account_number}><td>{row.account_number}</td><td>{row.label}</td><td>{row.amount}</td></tr>)}</tbody>
    <tfoot><tr><th colSpan={2}>Total {title.toLowerCase()}</th><td>{total}</td></tr></tfoot>
  </table></section>;
}

export default function StatementsPage() {
  const [setupView, setSetupView] = useState<ScreenView<Setup>>(() => beginLoad(idleView<Setup>(), false));
  const [year, setYear] = useState(0);
  const [report, setReport] = useState<ScreenView<Statements>>(idleView());
  const [downloadError, setDownloadError] = useState<RequestError | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [setupAttempt, setSetupAttempt] = useState(0);
  const setup = showsData(setupView) ? setupView.data : null;
  const data = showsData(report) ? report.data : null;
  useEffect(() => {
    const controller = new AbortController();
    defer(() => {
      if (controller.signal.aborted) return;
      setSetupView((current) => beginLoad(current, current.data !== null));
    });
    void request<Setup>("/setup").then((value) => {
      if (controller.signal.aborted) return;
      setSetupView(finishLoad(value, (loaded) => loaded.years.length === 0));
      if (value.years.length > 0) setYear((current) => current || value.years[0]?.id || 0);
    }, (reason: unknown) => {
      if (!controller.signal.aborted) {
        setSetupView((current) => failLoad(current, toApiError(reason), current.data !== null));
      }
    });
    return () => controller.abort();
  }, [setupAttempt]);
  useEffect(() => {
    let current = true;
    if (!year || setupView.phase !== "loaded") {
      defer(() => {
        if (current) setReport(idleView());
      });
      return () => { current = false; };
    }
    defer(() => {
      if (!current) return;
      setReport((previous) => beginLoad(previous, false));
    });
    void request<Statements>(`/years/${year}/statements`).then((value) => {
      if (current) setReport(finishLoad(value));
    }, (reason: unknown) => {
      if (current) setReport((previous) => failLoad(previous, toApiError(reason), false));
    });
    return () => { current = false; };
  }, [year, attempt, setupView.phase]);
  function refresh(nextYear = year) {
    setReport((previous) => beginLoad(previous, false));
    setYear(nextYear);
    setAttempt((value) => value + 1);
  }
  return <section className="ledger-page" aria-labelledby="statements-title" data-screen-phase={setupView.phase === "loaded" ? report.phase : setupView.phase}>
    <div className="heading-with-help">
      <h2 id="statements-title" tabIndex={-1}>États comptables</h2>
      <GlossaryTip id="bilan" />
      <GlossaryTip id="resultat-comptable" />
      <GlossaryTip id="fec" />
    </div>
    <p>Calculés sur les écritures validées. Centralisez le résultat ici. Le calcul fiscal, le pré-contrôle et la clôture sont dans Fiscalité LMNP.</p>
    <ScreenStatus
      state={setupView}
      onRetry={() => setSetupAttempt((value) => value + 1)}
      loading={<p role="status">Chargement des états…</p>}
      empty={<p>Créez un exercice dans Comptabilité pour consulter ses états.</p>}
    />
    {setup && setup.years.length > 0 && <div className="toolbar">
      <label>Exercice <select value={year} onChange={(event) => refresh(Number(event.target.value))}>{setup.years.map((item) => <option key={item.id} value={item.id}>{item.year}</option>)}</select></label>
      <button type="button" onClick={() => refresh()}>Actualiser les états</button>
      {setup.years.find((item) => item.id === year)?.status === "CLOSED"
        ? <button type="button" onClick={() => {
          setDownloadError(null);
          void downloadFiling(`/api/filing/years/${year}/fec`).catch((reason: unknown) => {
            setDownloadError(reason instanceof RequestError
              ? reason
              : new RequestError({ code: "HTTP_ERROR", message: "Le téléchargement du FEC a échoué." }, 0));
          });
        }}>Télécharger le FEC</button>
        : <p>Le FEC se télécharge dans Fiscalité LMNP, après le calcul fiscal et la clôture.</p>}
    </div>}
    {downloadError && <ApiErrorAlert detail={downloadError.detail} />}
    {year !== 0 && <OpeningPreview key={`${year}-${attempt}`} year={year} />}
    {year !== 0 && <ResultClosing key={`result-${year}-${attempt}`} year={year} />}
    {year !== 0 && (
      <ScreenStatus
        state={report}
        onRetry={() => refresh()}
        loading={<p role="status">Chargement des états…</p>}
        focusError
      />
    )}
    {data && <div aria-live="polite">
      <p>Période : {data.start_date} — {data.end_date}. Brouillons exclus : {data.excluded_draft_count}.</p>
      <h3>Compte de résultat</h3>
      <Accounts title="Produits" rows={data.income_statement.income} total={data.income_statement.total_income} />
      <Accounts title="Charges" rows={data.income_statement.expenses} total={data.income_statement.total_expenses} />
      <p><strong>Résultat comptable : {data.income_statement.result} €</strong></p>
      {data.presentation && <div>
        <h3>Présentation par rubriques</h3>
        <p>{data.presentation.reclassifications_applied ? "Reclassements appliqués." : "Aucun reclassement automatique. Un solde inhabituel reste dans sa rubrique."}</p>
        <ul>{data.presentation.warnings.map((warning) => <li key={warning.code + warning.message}>{warning.message}</li>)}</ul>
        {data.presentation.income_rubrics.map((rubric) => <Accounts key={rubric.code} title={rubric.label} rows={rubric.accounts} total={rubric.total} />)}
        {data.presentation.balance_rubrics.filter((rubric) => rubric.accounts.length > 0).map((rubric) => <Accounts key={rubric.code} title={rubric.label} rows={rubric.accounts} total={rubric.total} />)}
      </div>}
      <h3>Bilan par compte</h3>
      <p>Soldes signés selon le classement du plan de comptes. Les amortissements diminuent l’actif.</p>
      <Accounts title="Actif net" rows={data.balance_sheet.assets} total={data.balance_sheet.total_assets} />
      <Accounts title="Dettes" rows={data.balance_sheet.liabilities} total={data.balance_sheet.total_liabilities} />
      <Accounts title="Capitaux propres hors résultat" rows={data.balance_sheet.equity} total={data.balance_sheet.total_equity} />
      <p>Résultat de l’exercice : {data.balance_sheet.current_result} €</p>
      <p><strong>Total passif et capitaux propres : {data.balance_sheet.total_liabilities_and_equity} €</strong></p>
    </div>}
  </section>;
}
