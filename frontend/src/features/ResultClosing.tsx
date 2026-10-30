import { useEffect, useRef, useState } from "react";
import { amount, cents, request, type Account, type Entry, type Journal } from "../api/ledger";
import { centralizationCauses, describedBy } from "./actionCauses";
import PrerequisiteList from "./PrerequisiteList";
import GlossaryTip from "./GlossaryTip";
import { GLOSSARY } from "./glossary";
import { SaveNoticeHost } from "./LocalFeedback";
import { useSaveNotice } from "./localFeedback";
import MutationStatus from "./MutationStatus";
import { useMutation } from "./useMutation";
import { formatAmount, formatEuros } from "../lib/format";
import FrenchForm from "../lib/FrenchForm";
import FitSelect from "../lib/FitSelect";

interface PreviewLine { account_number: string; label: string; debit: string; credit: string }
interface ProposedAccount { number: string; label: string; account_type: string }
interface CentralPreview {
  result: string; result_account_prefix: string | null; excluded_draft_count: number;
  lines: PreviewLine[]; already_posted: boolean; year_status: string;
  proposed_accounts?: ProposedAccount[];
}
interface Proposal { source_account: string; label: string; amount: string }
interface ApproPreview { centralization_posted: boolean; proposals: Proposal[]; already_posted: boolean }
interface Saved {
  kind: "centralization" | "appropriation"; request_id: string; journal_code: string;
  piece_reference: string; justification: string; result_account: string | null;
  create_accounts: ProposedAccount[];
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
      if (!raw) return null;
      const value = JSON.parse(raw) as Saved;
      return { ...value, create_accounts: value.create_accounts ?? [] };
    } catch { return null; }
  });
  const [review, setReview] = useState(!!saved);
  const { notice, show, dismiss } = useSaveNotice();
  const [error, setError] = useState("");
  const { busy, step, run } = useMutation();
  const errorRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);

  async function load() {
    await run(async (report) => {
      report("Préparation de la centralisation…");
      setError(""); setPreview(null); setAppropriation(null); dismiss();
      try {
        const [central, accountsValue, journalsValue] = await Promise.all([
          request<CentralPreview>(`/years/${year}/centralization-preview`),
          request<Account[]>("/accounts"),
          request<Journal[]>("/journals"),
        ]);
        setPreview(central); setAccounts(accountsValue); setJournals(journalsValue);
        if (central.already_posted) setAppropriation(await request<ApproPreview>(`/years/${year}/appropriation-preview`));
      } catch (reason) { setError((reason as Error).message); }
    });
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
    const centralizing = !preview.already_posted;
    const resultAccount = centralizing && preview.result_account_prefix ? String(fields.get("result") ?? "") : null;
    if (centralizing && preview.result_account_prefix && !resultAccount) {
      setError("Choisissez le compte de résultat.");
      return;
    }
    const createAccounts = centralizing ? (preview.proposed_accounts ?? []).filter((account) => (
      account.number === resultAccount && !accounts.some((row) => row.number === account.number)
    )) : [];
    let expectedAmount = "";
    if (preview.already_posted) {
      try {
        expectedAmount = amount(cents(String(fields.get("amount") ?? "")));
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Montant invalide.");
        return;
      }
    }
    const next: Saved = preview.already_posted ? {
      kind: "appropriation", request_id: saved?.kind === "appropriation" ? saved.request_id : crypto.randomUUID(),
      journal_code: journal, piece_reference: piece, justification,
      result_account: null, create_accounts: [], source_account: String(fields.get("source")),
      target_account: String(fields.get("target")), expected_amount: expectedAmount,
    } : {
      kind: "centralization", request_id: saved?.kind === "centralization" ? saved.request_id : crypto.randomUUID(),
      journal_code: journal, piece_reference: piece, justification,
      result_account: resultAccount, create_accounts: createAccounts, expected_result: preview.result,
    };
    setError(""); setSaved(next); setReview(true);
  }

  async function post() {
    if (!saved) return;
    const requestBody = saved;
    await run(async (report) => {
      report(requestBody.kind === "centralization" ? "Centralisation du résultat…" : "Affectation du résultat…");
      setError("");
      try {
        sessionStorage.setItem(storageKey, JSON.stringify(requestBody));
        const path = requestBody.kind === "centralization" ? `/years/${year}/centralization` : `/years/${year}/appropriation`;
        const body = requestBody.kind === "centralization" ? {
          request_id: requestBody.request_id, journal_code: requestBody.journal_code, piece_reference: requestBody.piece_reference,
          justification: requestBody.justification, result_account: requestBody.result_account,
          create_accounts: requestBody.create_accounts ?? [], expected_result: requestBody.expected_result,
        } : {
          request_id: requestBody.request_id, journal_code: requestBody.journal_code, piece_reference: requestBody.piece_reference,
          justification: requestBody.justification, source_account: requestBody.source_account,
          target_account: requestBody.target_account, expected_amount: requestBody.expected_amount,
        };
        const response = await request<{ created: boolean; entry: Entry }>(path, "POST", body);
        const verb = response.created ? "validée" : "déjà enregistrée";
        const entryNumber = response.entry.entry_number ?? "résultat";
        const message = `Écriture ${entryNumber} ${verb}. Actualisez les états.`;
        sessionStorage.removeItem(storageKey);
        setSaved(null); setReview(false);
        show({
          kind: requestBody.kind === "centralization" ? GLOSSARY.centralisation.label : GLOSSARY.affectation.label,
          name: entryNumber,
          action: verb,
          targetId: "resultat-cloture",
          detail: message,
          next: requestBody.kind === "centralization"
            ? { label: "Affecter le résultat", href: "#result-title" }
            : { label: "Lancer le calcul fiscal", href: "/fiscalite#calcul-fiscal" },
        });
        if (requestBody.kind === "centralization") {
          const central = await request<CentralPreview>(`/years/${year}/centralization-preview`);
          const accountsValue = await request<Account[]>("/accounts");
          setPreview(central); setAccounts(accountsValue);
          if (central.already_posted) {
            setAppropriation(await request<ApproPreview>(`/years/${year}/appropriation-preview`));
          }
        }
      } catch (reason) { setError((reason as Error).message); }
    });
  }

  const general = journals.filter((journal) => journal.active && journal.journal_type === "GENERAL");
  const prefix = preview?.result_account_prefix;
  const proposed = (preview?.proposed_accounts ?? []).filter((account) => (
    !!prefix
    && !accounts.some((row) => row.number === account.number)
    && account.number.startsWith(prefix)
    && !account.number.startsWith("1209")
  ));
  const resultAccounts = accounts.filter((account) => account.active && !!prefix && account.number.startsWith(prefix) && !account.number.startsWith("1209"));
  const resultChoices = [
    ...resultAccounts.map((account) => ({ number: account.number, label: account.label, create: false })),
    ...proposed.map((account) => ({ number: account.number, label: account.label, create: true })),
  ];
  const shownLines = (preview?.lines ?? []).map((line) => (
    !line.account_number && review && saved?.result_account
      ? { ...line, account_number: saved.result_account }
      : line
  ));
  const missingResultAccount = !!prefix && resultChoices.length === 0;
  const centralCauses = preview
    ? centralizationCauses(preview.year_status, missingResultAccount, prefix ?? null)
    : [];
  const centralCauseId = "centralization-causes";
  return <section id="resultat-cloture" aria-labelledby="result-title">
    <SaveNoticeHost place="resultat-cloture" notice={notice} onDismiss={dismiss} />
    <div className="heading-with-help">
      <h3 id="result-title" tabIndex={-1}>Centraliser et affecter le résultat</h3>
      <GlossaryTip id="centralisation" />
      <GlossaryTip id="affectation" />
      <GlossaryTip id="compte-120-129" />
    </div>
    <p>Le serveur recalcule les montants. Confirmez le compte et la justification avant validation. Préparer, corriger ou quitter ne modifie pas le plan comptable. Cette étape ne clôture pas l’exercice. Ensuite, dans Fiscalité LMNP : calcul fiscal, pré-contrôle, puis clôture.</p>
    <button type="button" disabled={busy} aria-busy={busy || undefined} onClick={() => { void load(); }}>Préparer la centralisation</button>
    <MutationStatus step={step} />
    {error && <p role="alert" tabIndex={-1} ref={errorRef}>{error}</p>}
    {preview && !preview.already_posted && <FrenchForm onSubmit={(event) => { event.preventDefault(); if (review) void post(); else prepare(event.currentTarget); }}>
      <p>Résultat à centraliser : {formatEuros(preview.result)}. Brouillons exclus : {preview.excluded_draft_count}.</p>
      <table><caption>Écriture de centralisation proposée</caption>
        <thead><tr><th>Compte</th><th>Libellé</th><th>Débit</th><th>Crédit</th></tr></thead>
        <tbody>{shownLines.map((line) => <tr key={`${line.account_number}-${line.label}`}><td>{line.account_number || "À confirmer"}</td><td>{line.label}</td><td>{formatAmount(line.debit)}</td><td>{formatAmount(line.credit)}</td></tr>)}</tbody>
      </table>
      {!!proposed.length && <div>
        <p>Comptes absents, création proposée à la confirmation :</p>
        <ul>{proposed.map((account) => <li key={account.number}>{account.number} · {account.label}</li>)}</ul>
      </div>}
      {!review && <>
        <label>Journal<FitSelect name="journal" required>{general.map((journal) => <option key={journal.code} value={journal.code}>{journal.code}</option>)}</FitSelect></label>
        <label>Référence de pièce<input name="piece" required maxLength={200} /></label>
        {!!resultChoices.length && <label>Compte de résultat<FitSelect name="result" required defaultValue={saved?.result_account ?? resultChoices[0]?.number}>{resultChoices.map((account) => <option key={account.number} value={account.number}>{account.number} · {account.label}{account.create ? " (sera créé)" : ""}</option>)}</FitSelect></label>}
        <label>Justification<textarea name="justification" required minLength={10} maxLength={3000} /></label>
      </>}
      {review && saved && <p>Demande {saved.request_id} conservée dans cet onglet. Réessayez la même demande si la réponse a été perdue.</p>}
      {review && !!saved?.create_accounts?.length && <p>La confirmation crée {saved.create_accounts.map((account) => `${account.number} · ${account.label}`).join(", ")} dans la même opération que la centralisation.</p>}
      <button type="submit" disabled={busy || centralCauses.length > 0} aria-busy={busy || undefined} aria-describedby={describedBy(centralCauseId, centralCauses)}>{review ? "Confirmer la centralisation" : "Vérifier la centralisation"}</button>
      <PrerequisiteList id={centralCauseId} causes={centralCauses} />
      {review && <button type="button" disabled={busy} onClick={() => setReview(false)}>Corriger</button>}
    </FrenchForm>}
    {preview?.already_posted && appropriation && !appropriation.already_posted && <FrenchForm onSubmit={(event) => { event.preventDefault(); if (review) void post(); else prepare(event.currentTarget); }}>
      <p>La centralisation est déjà comptabilisée. Choisissez l’affectation du solde restant.</p>
      {!appropriation.proposals.length && <p>Aucun solde 120 ou 129 à affecter.</p>}
      {!!appropriation.proposals.length && <>
        {!review && <>
          <label>Compte source<FitSelect name="source" required onChange={(event) => {
            const chosen = appropriation.proposals.find((item) => item.source_account === event.target.value);
            const amount = event.currentTarget.form?.elements.namedItem("amount");
            if (chosen && amount instanceof HTMLInputElement) amount.value = chosen.amount;
          }}>{appropriation.proposals.map((item) => <option key={item.source_account} value={item.source_account}>{item.source_account} · {formatEuros(item.amount)}</option>)}</FitSelect></label>
          <label>Montant confirmé<input name="amount" required data-money="true" lang="fr" placeholder="1 234,56" inputMode="decimal" defaultValue={appropriation.proposals[0]?.amount ?? ""} /></label>
          <label>Compte d’affectation<FitSelect name="target" required>{accounts.filter((account) => account.active && account.account_type === "EQUITY" && !account.number.startsWith("120") && !account.number.startsWith("129")).map((account) => <option key={account.number} value={account.number}>{account.number} · {account.label}</option>)}</FitSelect></label>
          <label>Journal<FitSelect name="journal" required>{general.map((journal) => <option key={journal.code} value={journal.code}>{journal.code}</option>)}</FitSelect></label>
          <label>Référence de pièce<input name="piece" required maxLength={200} /></label>
          <label>Justification<textarea name="justification" required minLength={10} maxLength={3000} /></label>
        </>}
        {review && <p>Vérifiez le compte destinataire avant de valider l’affectation.</p>}
        <button type="submit" disabled={busy} aria-busy={busy || undefined}>{review ? "Confirmer l’affectation" : "Vérifier l’affectation"}</button>
      </>}
    </FrenchForm>}
    {appropriation?.already_posted && <p>L’affectation de cet exercice est déjà comptabilisée.</p>}
  </section>;
}
