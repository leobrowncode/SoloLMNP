import { useEffect, useRef, useState, type FormEvent } from "react";
import { request } from "../api/ledger";
import type { Opening } from "./OpeningPreview";

interface Continuity {
  balances_match: boolean; opening_entry_id: number | null; source_closed?: boolean;
  source_unchanged?: boolean; excluded_draft_count?: number;
  differences: { account_number: string; expected_balance: string; opening_balance: string; difference: string }[];
}

export default function OpeningPosting({ year, preview }: { year: number; preview: Opening | null }) {
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState("");
  const [control, setControl] = useState<Continuity | null>(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const generation = useRef(0);
  useEffect(() => () => { generation.current += 1; }, []);
  const blocked = !preview || !preview.preview_token || preview.total_debit === "0.00" || preview.warnings.some((warning) =>
    ["SOURCE_NOT_CLOSED", "SOURCE_DRAFTS", "TARGET_NOT_OPEN", "TARGET_HAS_ENTRIES", "INACTIVE_ACCOUNTS"].includes(warning.code));

  async function post(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preview || blocked || pending.current) return;
    const fields = new FormData(event.currentTarget);
    const id = ++generation.current;
    pending.current = true; setBusy(true); setError(""); setReceipt(""); setControl(null);
    try {
      const response = await request<{ created: boolean; entry: { entry_number: string } }>(`/years/${year}/opening`, "POST", {
        preview_token: preview.preview_token, journal_code: fields.get("journal"),
        piece_reference: fields.get("reference"), result_account: preview.result_line ? fields.get("result") : null,
      });
      if (id === generation.current) setReceipt(`Écriture ${response.entry.entry_number} ${response.created ? "créée et validée" : "déjà enregistrée"}. Actualisez les états pour consulter les nouveaux soldes.`);
    } catch (reason) {
      if (id === generation.current) setError((reason as Error).message);
    } finally {
      if (id === generation.current) { pending.current = false; setBusy(false); }
    }
  }
  async function check() {
    if (pending.current) return;
    const id = ++generation.current;
    pending.current = true; setBusy(true); setError(""); setControl(null);
    try {
      const value = await request<Continuity>(`/years/${year}/opening-continuity`);
      if (id === generation.current) setControl(value);
    } catch (reason) {
      if (id === generation.current) setError((reason as Error).message);
    } finally {
      if (id === generation.current) { pending.current = false; setBusy(false); }
    }
  }
  return <section aria-labelledby="opening-posting-title">
    <h4 id="opening-posting-title">Comptabiliser et contrôler les à-nouveaux</h4>
    <p>La génération valide une écriture à la date d’ouverture. Elle exige un exercice précédent clôturé sans brouillon et un exercice destinataire ouvert et vide. Le parcours de clôture reste à livrer en P7.</p>
    {preview && !receipt && <form onSubmit={(event) => { void post(event); }}>
      <fieldset disabled={blocked || busy}>
        <legend>Reprise avant affectation du résultat</legend>
        <label>Journal des à-nouveaux<input name="journal" defaultValue="AN" pattern="[A-Z0-9]{2,10}" required maxLength={10} /></label>
        <label>Référence de la pièce de reprise<input name="reference" required maxLength={200} /></label>
        {preview.result_line && <label>Compte de reprise du résultat<input name="result" required pattern="[1-7][0-9]{2,9}" maxLength={10} />
          <span>Compte actif de capitaux propres {preview.result_line.credit !== "0.00" ? "120 (hors 1209)" : "129"}, à créer dans le plan de comptes si absent. Aucune affectation automatique.</span>
        </label>}
        <button type="submit">Générer et valider les à-nouveaux</button>
      </fieldset>
    </form>}
    {receipt && <p role="status">{receipt}</p>}
    <button type="button" disabled={busy} onClick={() => { void check(); }}>Contrôler la continuité des à-nouveaux</button>
    {busy && <p role="status">Opération en cours…</p>}
    {error && <p role="alert">{error}</p>}
    {control && <div aria-live="polite">
      <p>{control.opening_entry_id === null ? "Aucun à-nouveau généré pour cet exercice." : control.balances_match ? "Les soldes de l’écriture de reprise correspondent aux soldes source." : "Des écarts ont été détectés dans les soldes repris."} Contrôle provisoire, sans certification des comptes annuels.</p>
      {control.opening_entry_id !== null && (!control.source_closed || !control.source_unchanged || !!control.excluded_draft_count) && <p role="alert">La source a changé, n’est plus clôturée ou contient des brouillons. Réexaminez la reprise.</p>}
      {control.differences.length > 0 && <table><caption>Écarts de reprise par compte</caption>
        <thead><tr><th>Compte</th><th>Attendu (€)</th><th>Repris (€)</th><th>Écart (€)</th></tr></thead>
        <tbody>{control.differences.map((row) => <tr key={row.account_number}><td>{row.account_number}</td><td>{row.expected_balance}</td><td>{row.opening_balance}</td><td>{row.difference}</td></tr>)}</tbody>
      </table>}
    </div>}
  </section>;
}
