import { useRef, useState } from "react";
import { amount, cents, request, type Account, type Entry, type EntryInput, type Journal, type Year } from "../api/ledger";

type InventoryInput = EntryInput & { justification: string; request_id: string };
const blankLine = () => ({ account_number: "", label: "", debit: "0.00", credit: "0.00" });
function restore(saved: string, year: number): InventoryInput {
  const value = JSON.parse(saved) as InventoryInput;
  if (!value || value.fiscal_year_id !== year ||
      ![value.request_id, value.journal_code, value.accounting_date, value.piece_date,
        value.piece_reference, value.label, value.justification].every((field) => typeof field === "string" && field.length > 0) ||
      !Array.isArray(value.lines) || value.lines.length < 2 || value.lines.length > 100 ||
      !value.lines.every((line) => line && [line.account_number, line.label, line.debit, line.credit].every((field) => typeof field === "string"))) {
    throw new Error("Demande conservée invalide.");
  }
  return value;
}

export default function InventoryForm({ year, accounts, journals, onPosted }: {
  year: Year; accounts: Account[]; journals: Journal[]; onPosted: () => void;
}) {
  const storageKey = `sololmnp.inventory.pending.${year.id}`;
  const [recovery] = useState(() => {
    try {
      const saved = sessionStorage.getItem(storageKey);
      return { value: saved ? restore(saved, year.id) : null, error: "" };
    } catch { return { value: null, error: "Impossible de lire la demande conservée. Vérifiez le stockage du navigateur avant de saisir un inventaire." }; }
  });
  const general = journals.filter((j) => j.active && j.journal_type === "GENERAL");
  const [draft, setDraft] = useState<EntryInput>({
    fiscal_year_id: year.id, journal_code: general[0]?.code ?? "",
    accounting_date: year.end_date, piece_date: year.end_date,
    piece_reference: "", label: "", lines: [blankLine(), blankLine()],
  });
  const [justification, setJustification] = useState("");
  const [review, setReview] = useState<InventoryInput | null>(recovery.value);
  const [attempted, setAttempted] = useState(!!recovery.value);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [error, setError] = useState(recovery.error);
  const [receipt, setReceipt] = useState<Entry | null>(null);
  const [checked, setChecked] = useState(false);
  let totals = "Montants au centime requis.";
  try {
    const lines = review?.lines ?? draft.lines;
    const debit = lines.reduce((sum, line) => sum + cents(line.debit), 0n);
    const credit = lines.reduce((sum, line) => sum + cents(line.credit), 0n);
    totals = `Débit : ${amount(debit)} € · Crédit : ${amount(credit)} € · Écart : ${amount(debit - credit)} €`;
  } catch { /* Invalid input is explained on review. */ }

  function prepare() {
    setError("");
    try {
      if (justification.trim().length < 10) throw new Error("Une justification de 10 caractères minimum est requise.");
      let balance = 0n;
      const lines = draft.lines.map((line) => {
        const debit = cents(line.debit), credit = cents(line.credit);
        if ((debit === 0n) === (credit === 0n)) throw new Error("Chaque ligne doit avoir exactement un côté positif.");
        if (!line.label.trim()) throw new Error("Renseignez le libellé de chaque ligne.");
        balance += debit - credit;
        return { ...line, label: line.label.trim(), debit: amount(debit), credit: amount(credit) };
      });
      if (balance !== 0n) throw new Error("Les débits et crédits doivent être équilibrés au centime.");
      if (!draft.label.trim() || !draft.piece_reference.trim()) throw new Error("Renseignez le libellé et la référence de pièce.");
      setReview({ ...draft, lines, justification: justification.trim(), request_id: crypto.randomUUID() });
    } catch (reason) { setError((reason as Error).message); }
  }
  async function post() {
    if (!review || pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try {
      // Persist the exact intention before any network request, including lost responses.
      sessionStorage.setItem(storageKey, JSON.stringify(review));
      setAttempted(true);
      const entry = await request<Entry>("/inventory", "POST", review);
      setReceipt(entry);
      sessionStorage.removeItem(storageKey);
      onPosted();
    } catch (reason) { setError((reason as Error).message); }
    finally { pending.current = false; setBusy(false); }
  }
  if (receipt) return <section><h3>Inventaire comptabilisé</h3><p role="status">Écriture {receipt.entry_number} · {receipt.label}. Consultez le journal et son historique pour retrouver la justification ou effectuer une extourne motivée.</p></section>;
  return <form className="entry-editor" onSubmit={(event) => { event.preventDefault(); if (review) void post(); else prepare(); }}>
    <h3>Inventaire manuel · exercice {year.year}</h3>
    <p>Choisissez les comptes et montants après vérification du traitement et du calcul. La confirmation valide définitivement l’écriture. La référence et la justification ne constituent pas un archivage de pièce.</p>
    {error && <p role="alert">{error}</p>}
    {!review && <fieldset disabled={year.status !== "OPEN" || !!recovery.error}>
      <legend>Saisie justifiée</legend>
      <label>Journal d’inventaire<select required value={draft.journal_code} onChange={(e) => setDraft({ ...draft, journal_code: e.target.value })}><option value="">Choisir un journal</option>{general.map((j) => <option key={j.code} value={j.code}>{j.code} · {j.label}</option>)}</select></label>
      {!general.length && <p>Aucun journal actif d’opérations diverses disponible.</p>}
      <label>Date comptable<input type="date" required min={year.start_date} max={year.end_date} value={draft.accounting_date} onChange={(e) => setDraft({ ...draft, accounting_date: e.target.value })} /></label>
      <label>Date de la pièce<input type="date" required value={draft.piece_date} onChange={(e) => setDraft({ ...draft, piece_date: e.target.value })} /></label>
      <label>Référence de la pièce<input required maxLength={200} value={draft.piece_reference} onChange={(e) => setDraft({ ...draft, piece_reference: e.target.value })} /></label>
      <label>Libellé de l’écriture<input required maxLength={300} value={draft.label} onChange={(e) => setDraft({ ...draft, label: e.target.value })} /></label>
      <label>Justification et calcul<textarea required minLength={10} maxLength={3000} value={justification} onChange={(e) => setJustification(e.target.value)} /></label>
      {draft.lines.map((line, index) => <fieldset key={index}><legend>Ligne {index + 1}</legend>
        <label>Compte<select required value={line.account_number} onChange={(e) => setDraft({ ...draft, lines: draft.lines.map((l, i) => i === index ? { ...l, account_number: e.target.value } : l) })}><option value="">Choisir un compte</option>{accounts.filter((a) => a.active).map((a) => <option key={a.number} value={a.number}>{a.number} · {a.label}</option>)}</select></label>
        {(["label", "debit", "credit"] as const).map((key) => <label key={key}>{key === "label" ? "Libellé" : key === "debit" ? "Débit (€)" : "Crédit (€)"}<input required maxLength={key === "label" ? 300 : 30} inputMode={key === "label" ? "text" : "decimal"} value={line[key]} onChange={(e) => setDraft({ ...draft, lines: draft.lines.map((l, i) => i === index ? { ...l, [key]: e.target.value } : l) })} /></label>)}
        <button type="button" disabled={draft.lines.length <= 2} onClick={() => setDraft({ ...draft, lines: draft.lines.filter((_, i) => i !== index) })}>Retirer la ligne {index + 1}</button>
      </fieldset>)}
      <button type="button" disabled={draft.lines.length >= 100} onClick={() => setDraft({ ...draft, lines: [...draft.lines, blankLine()] })}>Ajouter une ligne</button>
    </fieldset>}
    {review && <>
      <h4>Vérifier avant validation définitive</h4>
      <p>{review.journal_code} · {review.accounting_date} · {review.label}</p>
      <p>Pièce {review.piece_reference} du {review.piece_date}</p><p>{review.justification}</p>
      <table><caption>Lignes à comptabiliser</caption><thead><tr><th>Compte</th><th>Libellé</th><th>Débit €</th><th>Crédit €</th></tr></thead><tbody>{review.lines.map((line, i) => <tr key={i}><td>{line.account_number}</td><td>{line.label}</td><td>{line.debit}</td><td>{line.credit}</td></tr>)}</tbody></table>
      {!attempted && <button type="button" onClick={() => setReview(null)}>Corriger la saisie</button>}
      {attempted && <><p>Demande conservée dans cet onglet, y compris après rechargement. En cas de réponse perdue, réessayez la même demande. Ne fermez pas l’onglet avant résolution. Avant de l’abandonner, vérifiez le journal pour éviter une double saisie.</p>
        <label><input type="checkbox" disabled={busy} checked={checked} onChange={(e) => setChecked(e.target.checked)} />J’ai vérifié le journal et souhaite abandonner cette demande.</label>
        <button type="button" disabled={busy || !checked} onClick={() => {
          try { sessionStorage.removeItem(storageKey); setReview(null); setAttempted(false); setChecked(false); setError(""); }
          catch (reason) { setError((reason as Error).message); }
        }}>Abandonner après vérification</button></>}
    </>}
    <p aria-live="polite">{totals}</p>
    {year.status !== "OPEN" && !attempted && <p>Un exercice ouvert est requis.</p>}
    <button disabled={busy || !!recovery.error || (!attempted && (year.status !== "OPEN" || !general.length))}>{busy ? "Comptabilisation…" : review ? attempted ? "Réessayer la même demande" : "Confirmer la comptabilisation" : "Vérifier l’inventaire"}</button>
  </form>;
}
