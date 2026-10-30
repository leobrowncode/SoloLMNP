import { useEffect, useRef, useState } from "react";
import { request } from "../api/ledger";
import { formatAmount, formatIsoDate } from "../lib/format";
import { ledgerPath } from "../routing/paths";
import { EmptyState } from "./EmptyState";
import OpeningPosting from "./OpeningPosting";
import GlossaryTip from "./GlossaryTip";
import ScreenStatus from "./ScreenStatus";
import {
  beginLoad, failLoad, finishLoad, idleView, showsData, toApiError, type ScreenView,
} from "./screenState";

interface OpeningLine { account_number: string | null; label: string; debit: string; credit: string }
export interface Opening {
  preview_token?: string;
  source_end_date: string; opening_date: string; excluded_draft_count: number;
  lines: OpeningLine[]; result_line: OpeningLine | null;
  total_debit: string; total_credit: string;
  warnings: { code: string; message: string }[];
}

// The parent keys this component by exercise and refresh attempt.
export default function OpeningPreview({ year }: { year: number }) {
  const [view, setView] = useState<ScreenView<Opening>>(idleView());
  const data = showsData(view) ? view.data : null;
  const requestId = useRef(0);
  useEffect(() => () => { requestId.current += 1; }, []);
  async function load() {
    const id = ++requestId.current;
    setView((current) => beginLoad(current, false));
    try {
      const value = await request<Opening>(`/years/${year}/opening-preview`);
      if (id === requestId.current) {
        setView(finishLoad(value, (opening) => opening.lines.length === 0 && opening.result_line === null));
      }
    } catch (reason) {
      if (id === requestId.current) setView((current) => failLoad(current, toApiError(reason), false));
    }
  }
  return <section aria-labelledby="opening-title" data-screen-phase={view.phase}>
    <div className="heading-with-help">
      <h3 id="opening-title" tabIndex={-1}>Préparer les à-nouveaux de cet exercice</h3>
      <GlossaryTip id="a-nouveaux" />
    </div>
    <p>La prévisualisation depuis l’exercice précédent ne crée aucune écriture. Vérifiez les soldes avant de demander leur comptabilisation.</p>
    <button
      type="button"
      onClick={() => { void load(); }}
      disabled={view.phase === "loading"}
      aria-describedby={view.phase === "loading" ? "opening-loading" : undefined}
    >Prévisualiser les à-nouveaux</button>
    <ScreenStatus
      state={view}
      onRetry={() => { void load(); }}
      loading={<p id="opening-loading" role="status">Chargement des soldes à reprendre…</p>}
      empty={<EmptyState title="Aucun solde à reprendre." reason="L’exercice précédent n’a pas de solde validé à reporter. Vérifiez sa clôture avant de préparer les à-nouveaux." action={{ label: "Ouvrir le journal", href: ledgerPath("Journal") }} />}
    />
    {data && <div aria-live="polite">
      <p>Soldes au {formatIsoDate(data.source_end_date)} pour l’ouverture du {formatIsoDate(data.opening_date)}. Brouillons exclus : {data.excluded_draft_count}.</p>
      <ul>{data.warnings.map((warning) => <li key={warning.code}>{warning.message}</li>)}</ul>
      <table><caption>Soldes à reprendre — prévisualisation provisoire</caption>
        <thead><tr><th>Compte</th><th>Libellé</th><th>Débit (€)</th><th>Crédit (€)</th></tr></thead>
        <tbody>{[...data.lines, ...(data.result_line ? [data.result_line] : [])].map((row) => <tr key={row.account_number ?? "result"}>
          <td>{row.account_number ?? "À déterminer"}</td><td>{row.label}</td><td>{formatAmount(row.debit)}</td><td>{formatAmount(row.credit)}</td>
        </tr>)}</tbody>
        <tfoot><tr><th colSpan={2}>Totaux incluant le résultat précédent</th><td>{formatAmount(data.total_debit)}</td><td>{formatAmount(data.total_credit)}</td></tr></tfoot>
      </table>
    </div>}
    <OpeningPosting key={data ? "loaded" : "empty"} year={year} preview={data} />
  </section>;
}
