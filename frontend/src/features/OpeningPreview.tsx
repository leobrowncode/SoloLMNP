import { useEffect, useRef, useState } from "react";
import { request } from "../api/ledger";
import OpeningPosting from "./OpeningPosting";

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
  const [data, setData] = useState<Opening | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const requestId = useRef(0);
  useEffect(() => () => { requestId.current += 1; }, []);
  async function load() {
    const id = ++requestId.current;
    setData(null); setError(""); setLoading(true);
    try {
      const value = await request<Opening>(`/years/${year}/opening-preview`);
      if (id === requestId.current) setData(value);
    } catch (reason) {
      if (id === requestId.current) setError((reason as Error).message);
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }
  return <section aria-labelledby="opening-title">
    <h3 id="opening-title">Préparer les à-nouveaux de cet exercice</h3>
    <p>La prévisualisation depuis l’exercice précédent ne crée aucune écriture. Vérifiez les soldes avant de demander leur comptabilisation.</p>
    <button type="button" onClick={() => { void load(); }} disabled={loading}>Prévisualiser les à-nouveaux</button>
    {loading && <p role="status">Chargement des soldes à reprendre…</p>}
    {error && <p role="alert">{error}</p>}
    {data && <div aria-live="polite">
      <p>Soldes au {data.source_end_date} pour l’ouverture du {data.opening_date}. Brouillons exclus : {data.excluded_draft_count}.</p>
      <ul>{data.warnings.map((warning) => <li key={warning.code}>{warning.message}</li>)}</ul>
      <table><caption>Soldes à reprendre — prévisualisation provisoire</caption>
        <thead><tr><th>Compte</th><th>Libellé</th><th>Débit (€)</th><th>Crédit (€)</th></tr></thead>
        <tbody>{[...data.lines, ...(data.result_line ? [data.result_line] : [])].map((row) => <tr key={row.account_number ?? "result"}>
          <td>{row.account_number ?? "À déterminer"}</td><td>{row.label}</td><td>{row.debit}</td><td>{row.credit}</td>
        </tr>)}</tbody>
        <tfoot><tr><th colSpan={2}>Totaux incluant le résultat précédent</th><td>{data.total_debit}</td><td>{data.total_credit}</td></tr></tfoot>
      </table>
    </div>}
    <OpeningPosting key={data ? "loaded" : "empty"} year={year} preview={data} />
  </section>;
}
