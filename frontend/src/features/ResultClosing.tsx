import { useEffect, useRef, useState } from "react";
import { request, type Account, type Entry, type Journal } from "../api/ledger";

interface PreviewLine { account_number: string; label: string; debit: string; credit: string }
interface CentralPreview {
  result: string; result_account_prefix: string | null; excluded_draft_count: number;
  lines: PreviewLine[]; already_posted: boolean; year_status: string;
}
interface Proposal { source_account: string; label: string; amount: string }
interface ApproPreview { centralization_posted: boolean; proposals: Proposal[]; already_posted: boolean }
interface Saved {
  kind: "centralization" | "appropriation"; request_id: string; journal_code: string;
  piece_reference: string; justification: string; result_account: string | null;
  expected_result?: string; source_account?: string; target_account?: string; expected_amount?: string;
}

export default function ResultClosing({ year }: { year: number }) {
  const storageKey = `sololmnp.result.pending.${year}`;
  const [preview, setPreview] = useState<CentralPreview | null>(null);
  const [appropriation, setAppropriation] = useState<ApproPreview | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [journals, setJournals] = useState<Journal[]>([]);
  const [saved, setSaved] = useState<Saved | null>(() => {
    try {
      const raw = sessionStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) as Saved : null;
    } catch { return null; }
  });
  const [review, setReview] = useState(!!saved);
  const [receipt, setReceipt] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const errorRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);

  async function load() {
    setError(""); setPreview(null); setAppropriation(null); setReceipt("");
    try {
      const [central, loadedAccounts, journalsValue] = await Promise.all([
        request<CentralPreview>(`/years/${year}/centralization-preview`),
        request<Account[]>("/accounts"),
        request<Journal[]>("/journals"),
      ]);
      let accountsValue = loadedAccounts;
      for (const [number, label] of [
        ["120000", "Résultat de l’exercice (bénéfice)"],
        ["129000", "Résultat de l’exercice (déficit)"],
      ] as const) {
        if (!accountsValue.some((account) => account.number === number)) {
          await request("/accounts", "POST", { number, label, account_type: "EQUITY" });
        }
      }
      accountsValue = await request<Account[]>("/accounts");
      setPreview(central); setAccounts(accountsValue); setJournals(journalsValue);
      if (central.already_posted) setAppropriation(await request<ApproPreview>(`/years/${year}/appropriation-preview`));
    } catch (reason) { setError((reason as Error).message); }
  }

  function prepare(form: HTMLFormElement) {
    if (!preview) return;
    const fields = new FormData(form);
    const justification = String(fields.get("justification") ?? "").trim();
    const piece = String(fields.get("piece") ?? "").trim();
    const journal = String(fields.get("journal") ?? "");
    if (justification.length < 10 || !piece || !journal) {
      setError("Renseignez le journal, la pièce et une justification d’au moins 10 caractères.");
      return;
    }
    const next: Saved = preview.already_posted ? {
      kind: "appropriation", request_id: saved?.kind === "appropriation" ? saved.request_id : crypto.randomUUID(),
      journal_code: journal, piece_reference: piece, justification,
      result_account: null, source_account: String(fields.get("source")),
      target_account: String(fields.get("target")), expected_amount: String(fields.get("amount")),
    } : {
      kind: "centralization", request_id: saved?.kind === "centralization" ? saved.request_id : crypto.randomUUID(),
      journal_code: journal, piece_reference: piece, justification,
      result_account: preview.result_account_prefix ? String(fields.get("result")) : null,
      expected_result: preview.result,
    };
    setError(""); setSaved(next); setReview(true);
  }

  async function post() {
    if (!saved || pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(saved));
      const path = saved.kind === "centralization" ? `/years/${year}/centralization` : `/years/${year}/appropriation`;
      const body = saved.kind === "centralization" ? {
        request_id: saved.request_id, journal_code: saved.journal_code, piece_reference: saved.piece_reference,
        justification: saved.justification, result_account: saved.result_account, expected_result: saved.expected_result,
      } : {
        request_id: saved.request_id, journal_code: saved.journal_code, piece_reference: saved.piece_reference,
        justification: saved.justification, source_account: saved.source_account,
        target_account: saved.target_account, expected_amount: saved.expected_amount,
      };
      const response = await request<{ created: boolean; entry: Entry }>(path, "POST", body);
      setReceipt(`Écriture ${response.entry.entry_number} ${response.created ? "validée" : "déjà enregistrée"}. Actualisez les états.`);
      sessionStorage.removeItem(storageKey);
      setSaved(null); setReview(false);
    } catch (reason) { setError((reason as Error).message); }
    finally { pending.current = false; setBusy(false); }
  }

  const general = journals.filter((journal) => journal.active && journal.journal_type === "GENERAL");
  const resultAccounts = accounts.filter((account) => account.active && preview?.result_account_prefix && account.number.startsWith(preview.result_account_prefix) && !account.number.startsWith("1209"));
  return <section aria-labelledby="result-title">
    <h3 id="result-title">Centraliser et affecter le résultat</h3>
    <p>Le serveur recalcule les montants. Confirmez le compte et la justification avant validation. Cette étape ne clôture pas l’exercice. Ensuite, dans Fiscalité LMNP : calcul fiscal, pré-contrôle, puis clôture.</p>
    <button type="button" onClick={() => { void load(); }}>Préparer la centralisation</button>
    {error && <p role="alert" tabIndex={-1} ref={errorRef}>{error}</p>}
    {receipt && <p role="status">{receipt}</p>}
    {preview && !preview.already_posted && <form onSubmit={(event) => { event.preventDefault(); if (review) void post(); else prepare(event.currentTarget); }}>
      <p>Résultat à centraliser : {preview.result} €. Brouillons exclus : {preview.excluded_draft_count}.</p>
      <table><caption>Écriture de centralisation proposée</caption>
        <thead><tr><th>Compte</th><th>Libellé</th><th>Débit</th><th>Crédit</th></tr></thead>
        <tbody>{preview.lines.map((line) => <tr key={`${line.account_number}-${line.label}`}><td>{line.account_number || "À confirmer"}</td><td>{line.label}</td><td>{line.debit}</td><td>{line.credit}</td></tr>)}</tbody>
      </table>
      {!review && <>
        <label>Journal<select name="journal" required>{general.map((journal) => <option key={journal.code} value={journal.code}>{journal.code}</option>)}</select></label>
        <label>Référence de pièce<input name="piece" required maxLength={200} /></label>
        {preview.result_account_prefix && <label>Compte de résultat<select name="result" required>{resultAccounts.map((account) => <option key={account.number} value={account.number}>{account.number} · {account.label}</option>)}</select></label>}
        <label>Justification<textarea name="justification" required minLength={10} maxLength={3000} /></label>
      </>}
      {review && saved && <p>Demande {saved.request_id} conservée dans cet onglet. Réessayez la même demande si la réponse a été perdue.</p>}
      <button type="submit" disabled={busy || preview.year_status !== "OPEN"}>{review ? "Confirmer la centralisation" : "Vérifier la centralisation"}</button>
      {review && <button type="button" onClick={() => setReview(false)}>Corriger</button>}
    </form>}
    {preview?.already_posted && appropriation && !appropriation.already_posted && <form onSubmit={(event) => { event.preventDefault(); if (review) void post(); else prepare(event.currentTarget); }}>
      <p>La centralisation est déjà comptabilisée. Choisissez l’affectation du solde restant.</p>
      {!appropriation.proposals.length && <p>Aucun solde 120 ou 129 à affecter.</p>}
      {!!appropriation.proposals.length && <>
        {!review && <>
          <label>Compte source<select name="source" required onChange={(event) => {
            const chosen = appropriation.proposals.find((item) => item.source_account === event.target.value);
            const amount = event.currentTarget.form?.elements.namedItem("amount");
            if (chosen && amount instanceof HTMLInputElement) amount.value = chosen.amount;
          }}>{appropriation.proposals.map((item) => <option key={item.source_account} value={item.source_account}>{item.source_account} · {item.amount} €</option>)}</select></label>
          <label>Montant confirmé<input name="amount" required defaultValue={appropriation.proposals[0]?.amount ?? ""} /></label>
          <label>Compte d’affectation<select name="target" required>{accounts.filter((account) => account.active && account.account_type === "EQUITY" && !account.number.startsWith("120") && !account.number.startsWith("129")).map((account) => <option key={account.number} value={account.number}>{account.number} · {account.label}</option>)}</select></label>
          <label>Journal<select name="journal" required>{general.map((journal) => <option key={journal.code} value={journal.code}>{journal.code}</option>)}</select></label>
          <label>Référence de pièce<input name="piece" required maxLength={200} /></label>
          <label>Justification<textarea name="justification" required minLength={10} maxLength={3000} /></label>
        </>}
        {review && <p>Vérifiez le compte destinataire avant de valider l’affectation.</p>}
        <button type="submit" disabled={busy}>{review ? "Confirmer l’affectation" : "Vérifier l’affectation"}</button>
      </>}
    </form>}
    {appropriation?.already_posted && <p>L’affectation de cet exercice est déjà comptabilisée.</p>}
  </section>;
}
