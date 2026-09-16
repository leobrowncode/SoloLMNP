import { useEffect, useState } from "react";
import { request, type Account, type Setup, type Entry } from "../api/ledger";
import { operationsRequest as api, type Property, type Bank, type Loan, type Operation, type BankTransaction, type ImportPreview } from "../api/operations";
import ReviewForm, { type Field } from "./ReviewForm";
import "./ledger.css";

const kindLabel: Record<string, string> = { REVENUE: "Recette", EXPENSE: "Dépense", SETTLEMENT: "Règlement", LOAN_PAYMENT: "Échéance", LOAN_FUNDING: "Déblocage" };
interface Editor { title: string; fields: Field[]; path: string; retry?: boolean; fixed?: Record<string, unknown> }
export default function OperationsPage() {
  const [tab, setTab] = useState("Transactions");
  const [setup, setSetup] = useState<Setup | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [banks, setBanks] = useState<Bank[]>([]);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [operations, setOperations] = useState<Operation[]>([]);
  const [bankId, setBankId] = useState(0);
  const [transactions, setTransactions] = useState<BankTransaction[]>([]);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [csv, setCsv] = useState("");
  const [editor, setEditor] = useState<Editor | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const [bankOffset, setBankOffset] = useState(0);
  const [details, setDetails] = useState<Entry | null>(null);
  const [matchCandidates, setMatchCandidates] = useState<{ transaction: BankTransaction; lines: { id: number; label: string }[] } | null>(null);
  const [loaded, setLoaded] = useState("");
  const key = JSON.stringify([revision, offset]);
  const [bankLoaded, setBankLoaded] = useState("");
  const bankKey = JSON.stringify([revision, bankId, bankOffset]);

  useEffect(() => {
    let active = true;
    void Promise.all([request<Setup>("/setup"), request<Account[]>("/accounts"), api<Property[]>("/properties"), api<Bank[]>("/banks"), api<Loan[]>("/loans"), api<Operation[]>("?limit=50&offset=" + offset)]).then(([s, a, p, b, l, o]) => {
      if (!active) return;
      setSetup(s); setAccounts(a); setProperties(p); setBanks(b); setLoans(l); setOperations(o);
      setBankId((current) => current || b[0]?.id || 0); setLoaded(key);
    }).catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [revision, offset, key]);
  useEffect(() => {
    if (!bankId) return;
    let active = true;
    void api<BankTransaction[]>("/bank/transactions?bank_account_id=" + bankId + "&limit=50&offset=" + bankOffset).then((items) => {
      if (active) { setTransactions(items); setBankLoaded(bankKey); }
    }).catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [bankId, revision, bankOffset, bankKey]);

  const choices = (items: { id: number; name: string }[]): [string, string][] => items.map((item) => [String(item.id), item.name]);
  const propertyField: Field = { name: "property_id", label: "Bien", type: "number", choices: choices(properties) };
  const bankField: Field = { name: "bank_account_id", label: "Compte bancaire", type: "number", choices: choices(banks), value: String(bankId) };
  const yearField: Field = { name: "fiscal_year_id", label: "Exercice de comptabilisation", type: "number", choices: setup?.years.filter((y) => y.status === "OPEN").map((y) => [String(y.id), String(y.year)]) ?? [] };
  const dateFields: Field[] = [{ name: "date", label: "Date comptable", type: "date" }, { name: "piece_reference", label: "Référence justificative" }];
  const accountField = (name: string, label: string, prefix: string, value?: string): Field => ({
    name, label, value, choices: accounts.filter((a) => a.active && a.number.startsWith(prefix)).map((a) => [a.number, a.number + " · " + a.label]),
  });
  const settlementFields: Field[] = [yearField, ...dateFields, bankField, { name: "amount", label: "Montant (€)", money: true }];

  function newOperation(kind: "REVENUE" | "EXPENSE", transaction?: BankTransaction) {
    setEditor({
      title: kind === "REVENUE" ? "Enregistrer une recette" : "Enregistrer une dépense", path: "", retry: true,
      fixed: { kind, ...(transaction ? { bank_transaction_id: transaction.id } : {}) },
      fields: [propertyField, yearField,
        { ...dateFields[0]!, value: transaction?.date },
        { name: "piece_date", label: "Date de la pièce", type: "date", value: transaction?.date },
        { ...dateFields[1]!, value: transaction?.external_reference },
        { name: "description", label: "Description", value: transaction?.label },
        { name: "counterparty", label: kind === "REVENUE" ? "Locataire / client" : "Fournisseur" },
        { name: "amount", label: "Montant intégral (€)", money: true, value: transaction?.amount.replace("-", "") },
        accountField("accounting_account", "Compte de " + (kind === "REVENUE" ? "produit" : "charge"), kind === "REVENUE" ? "7" : "6", kind === "REVENUE" ? "706000" : "616000"),
        { ...bankField, label: "Règlement à cette même date", optional: !transaction, choices: transaction ? choices(banks.filter((b) => b.id === bankId)) : [["", "Non réglé : compte client/fournisseur"], ...choices(banks)], value: transaction ? String(bankId) : "" },
        ...(kind === "EXPENSE" ? [
          { name: "deductible_percentage", label: "Part déductible envisagée (%) — à vérifier fiscalement", money: true, value: "100.00" },
          { name: "fiscal_treatment", label: "Traitement fiscal envisagé", choices: [["REQUIRES_REVIEW", "À vérifier"], ["DEDUCTIBLE", "Déductible"], ["PARTIAL", "Partiellement déductible"], ["NON_DEDUCTIBLE", "Non déductible"]] } as Field,
        ] : []),
      ],
    });
  }
  async function save(data: Record<string, unknown>) {
    if (!editor) return;
    await api(editor.path, "POST", { ...data, ...editor.fixed });
    setEditor(null); setDetails(null); setMessage("Enregistrement effectué."); setRevision((v) => v + 1);
  }
  async function action(fn: () => Promise<unknown>) {
    setBusy(true); setError(""); setMessage("");
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : "Service indisponible."); }
    finally { setBusy(false); }
  }
  async function findCandidates(transaction: BankTransaction) {
    const y = setup?.years.find((item) => item.start_date <= transaction.date && transaction.date <= item.end_date);
    if (!y) throw new Error("Créez l’exercice correspondant dans Comptabilité.");
    const number = banks.find((b) => b.id === bankId)?.account_number;
    const result = await request<{ lines: { entry_id: number }[] }>("/years/" + y.id + "/general-ledger?account_number=" + number);
    const uniqueIds = [...new Set(result.lines.map((line) => line.entry_id))];
    if (uniqueIds.length > 500) throw new Error("Plus de 500 écritures candidates : utilisez le rapprochement par l’API ou affinez votre compte bancaire.");
    const entries = await Promise.all(uniqueIds.map((id) => request<Entry>("/entries/" + id)));
    const lines = entries.flatMap((entry) => entry.lines.filter((line) => line.account_number === number && (transaction.amount.startsWith("-") ? line.credit === transaction.amount.slice(1) && line.debit === "0.00" : line.debit === transaction.amount && line.credit === "0.00")).map((line) => ({
      id: line.id,
      label: entry.entry_number + " · " + entry.accounting_date + " · " + entry.label,
    })));
    setMatchCandidates({ transaction, lines });
  }

  return <section id="operations" className="ledger-page" aria-labelledby="operations-title">
    <p className="eyebrow">DU JUSTIFICATIF À L’ÉCRITURE</p><h2 id="operations-title">Opérations & banque</h2>
    <p>Enregistrez les produits et charges à leur date comptable. Pour un règlement à une autre date, choisissez « Non réglé », puis saisissez le règlement séparément.</p>
    {error && <p role="alert" className="ledger-error">{error}</p>}{message && <p role="status">{message}</p>}
    {!setup ? <p>Chargement…</p> : !setup.activity ? <p>Initialisez votre activité et votre exercice dans Comptabilité avant de saisir vos opérations.</p> : <>
      <nav aria-label="Gestion des opérations">{["Transactions", "Banque", "Biens", "Emprunts"].map((name) => <button key={name} aria-pressed={tab === name} onClick={() => { setTab(name); setEditor(null); setDetails(null); }}>{name}</button>)}</nav>
      {editor && <ReviewForm key={JSON.stringify(editor)} title={editor.title} fields={editor.fields} onSave={save} onCancel={() => setEditor(null)} retryId={editor.retry} />}
      {tab === "Transactions" && <>
        <button disabled={!properties.length || !setup.years.some((y) => y.status === "OPEN")} onClick={() => newOperation("REVENUE")}>Nouvelle recette</button>
        <button disabled={!properties.length || !setup.years.some((y) => y.status === "OPEN")} onClick={() => newOperation("EXPENSE")}>Nouvelle dépense</button>
        {!properties.length && <p>Ajoutez d’abord un bien dans l’onglet Biens.</p>}
        <p>Le pourcentage fiscal est une information à vérifier ; il ne réduit jamais le montant de l’écriture.</p>
        {loaded !== key ? <p>Chargement des opérations…</p> : operations.map((row) => <article key={row.id} className="entry-card">
          <h3>{kindLabel[row.kind]} · {row.description} · {row.amount} €</h3>
          <p>{row.date} · {row.counterparty} · {row.status === "REVERSED" ? "Extournée" : "Comptabilisée"}{row.remaining_to_settle !== null && " · Reste à régler : " + row.remaining_to_settle + " €"}</p>
          {row.kind === "LOAN_PAYMENT" && <p>Capital {row.principal} € · Intérêts {row.interest} € · Assurance {row.insurance} € · Frais {row.other_costs} €</p>}
          <button onClick={() => { void action(async () => setDetails(await request<Entry>("/entries/" + row.accounting_entry_id))); }}>Voir l’écriture</button>
          {row.status !== "REVERSED" && row.remaining_to_settle && row.remaining_to_settle !== "0.00" && <button disabled={!banks.length} onClick={() => setEditor({ title: "Régler : " + row.description, path: "/" + row.id + "/settle", retry: true, fields: settlementFields.map((f) => f.name === "amount" ? { ...f, value: row.remaining_to_settle! } : f) })}>Enregistrer un règlement</button>}
          {row.status !== "REVERSED" && <button onClick={() => setEditor({ title: "Extourner : " + row.description, path: "/" + row.id + "/reverse", fields: [{ name: "accounting_date", label: "Date d’extourne", type: "date" }, { name: "piece_reference", label: "Pièce d’extourne" }, { name: "reason", label: "Motif (au moins 5 caractères)" }] })}>Extourner l’opération</button>}
        </article>)}
        <button disabled={!offset} onClick={() => setOffset(offset - 50)}>Opérations précédentes</button><button disabled={operations.length < 50} onClick={() => setOffset(offset + 50)}>Opérations suivantes</button>
      </>}
      {details && <div className="ledger-table"><h3>{details.entry_number} · {details.label}</h3><table><thead><tr><th>Compte</th><th>Libellé</th><th>Débit</th><th>Crédit</th></tr></thead><tbody>{details.lines.map((line, i) => <tr key={i}><td>{line.account_number}</td><td>{line.label}</td><td>{line.debit}</td><td>{line.credit}</td></tr>)}</tbody></table></div>}
      {tab === "Biens" && <>
        <p>Le registre des biens ne génère pas d’écriture d’acquisition. Les immobilisations et leur financement seront rapprochés dans les phases suivantes.</p>
        <button onClick={() => setEditor({ title: "Ajouter un bien", path: "/properties", fields: [
          { name: "name", label: "Nom du bien" }, { name: "address", label: "Adresse" }, { name: "acquisition_date", label: "Date d’acquisition", type: "date" },
          { name: "rental_start_date", label: "Début de location", type: "date", optional: true },
          { name: "acquisition_price", label: "Prix d’acquisition (€)", money: true }, { name: "acquisition_costs", label: "Frais d’acquisition (€)", money: true },
          { name: "land_value", label: "Valeur du terrain (€)", money: true }, { name: "building_value", label: "Valeur du bâtiment (€)", money: true },
        ] })}>Ajouter un bien</button>
        {properties.map((p) => <article key={p.id} className="entry-card"><h3>{p.name}</h3><p>Acquisition : {p.acquisition_price} € · Terrain : {p.land_value} € · Bâtiment : {p.building_value} €</p></article>)}
      </>}
      {tab === "Emprunts" && <>
        <p>Chaque emprunt utilise un compte 164 distinct. Son capital restant est lu dans la comptabilité. Pour un emprunt existant, saisissez d’abord les à-nouveaux justifiés ; aucun financement historique n’est inventé.</p>
        <button disabled={!properties.length} onClick={() => setEditor({ title: "Ajouter un emprunt", path: "/loans", fields: [
          propertyField, { name: "lender", label: "Prêteur" }, { name: "start_date", label: "Début de l’emprunt", type: "date" },
          { name: "initial_principal", label: "Capital initial (€)", money: true }, { name: "interest_rate", label: "Taux annuel (%) — informatif", money: true },
          { name: "duration_months", label: "Durée en mois", type: "number" },
          { name: "monthly_payment", label: "Mensualité contractuelle (€) — informative", money: true, value: "0.00" },
          { name: "monthly_insurance", label: "Assurance mensuelle contractuelle (€) — informative", money: true, value: "0.00" },
          accountField("principal_account", "Compte de capital dédié", "164"),
        ] })}>Ajouter un emprunt</button>
        {loans.map((l) => <article className="entry-card" key={l.id}><h3>{l.lender}</h3><p>Capital initial : {l.initial_principal} € · Solde comptable : {l.remaining_principal} € · Mensualité contractuelle : {l.monthly_payment} € + assurance {l.monthly_insurance} € · Compte {l.principal_account}</p>
          <button disabled={!banks.length} onClick={() => setEditor({ title: "Déblocage initial : " + l.lender, path: "/loans/" + l.id + "/fund", retry: true, fields: settlementFields.map((f) => f.name === "amount" ? { ...f, value: l.initial_principal } : f) })}>Enregistrer le déblocage</button>
          <button disabled={!banks.length} onClick={() => setEditor({ title: "Échéance : " + l.lender, path: "/loans/" + l.id + "/payments", retry: true, fields: [
            ...settlementFields, ...[["principal", "Capital remboursé (€)"], ["interest", "Intérêts (€)"], ["insurance", "Assurance (€)"], ["other_costs", "Autres frais (€)"]].map(([name, label]) => ({ name: name!, label: label!, money: true })),
          ] })}>Saisir une échéance</button>
        </article>)}
      </>}
      {tab === "Banque" && <>
        <button onClick={() => setEditor({ title: "Ajouter un compte bancaire", path: "/banks", fields: [{ name: "name", label: "Nom du compte bancaire" }, accountField("account_number", "Compte comptable dédié", "512")] })}>Ajouter un compte bancaire</button>
        {!!banks.length && <>
          <label>Banque sélectionnée<select value={bankId} onChange={(e) => { setBankId(Number(e.target.value)); setBankOffset(0); setPreview(null); setEditor(null); setMatchCandidates(null); }}>{banks.map((b) => <option key={b.id} value={b.id}>{b.name} · {b.account_number}</option>)}</select></label>
          <details><summary>Importer un relevé CSV</summary>
            <p>UTF-8, séparateur point-virgule, en-tête exact : <code>date;label;amount;reference</code>. Date AAAA-MM-JJ, montant signé. La référence doit identifier chaque mouvement de façon stable et unique dans cette banque. L’import seul ne comptabilise rien.</p>
            <label>Fichier CSV (1 Mo maximum)<input type="file" accept=".csv,text/csv" onChange={(e) => {
              const file = e.target.files?.[0]; setPreview(null);
              if (file) void action(async () => { if (file.size > 1_000_000) throw new Error("Fichier trop volumineux."); setCsv(await file.text()); });
            }} /></label>
            <label>Contenu CSV<textarea rows={6} value={csv} onChange={(e) => { setCsv(e.target.value); setPreview(null); }} /></label>
            <button disabled={busy || !csv} onClick={() => { void action(async () => setPreview(await api<ImportPreview>("/bank/preview", "POST", { bank_account_id: bankId, content: csv }))); }}>Prévisualiser l’import</button>
            {preview && <><p>{preview.count} mouvement(s) · {preview.rows.filter((r) => r.duplicate).length} déjà importé(s)</p>
              <div className="ledger-table"><table><thead><tr><th>Date</th><th>Libellé</th><th>Montant</th><th>Déjà importé</th><th>Compte suggéré à vérifier</th></tr></thead><tbody>{preview.rows.map((row) => <tr key={row.reference}><td>{row.date}</td><td>{row.label}</td><td>{row.amount}</td><td>{row.duplicate ? "Oui" : "Non"}</td><td>{row.suggested_account || "À choisir"}</td></tr>)}</tbody></table></div>
              <button disabled={busy} onClick={() => { void action(async () => { const result = await api<ImportPreview>("/bank/import", "POST", { bank_account_id: bankId, content: csv }); setMessage(result.imported + " mouvement(s) importé(s), en attente de rapprochement."); setPreview(null); setRevision((v) => v + 1); }); }}>Confirmer l’import des mouvements</button>
            </>}
          </details>
          {bankLoaded !== bankKey ? <p>Chargement du relevé…</p> : transactions.map((t) => <article key={t.id} className="entry-card"><h3>{t.label} · {t.amount} €</h3><p>{t.date} · {t.external_reference} · {t.matched_entry_id ? "Rapproché avec l’écriture #" + t.matched_entry_id : "À rapprocher"}</p>
            {!t.matched_entry_id ? <>
              <button disabled={busy} onClick={() => { void action(() => findCandidates(t)); }}>Rapprocher une écriture existante</button>
              <button disabled={!properties.length} onClick={() => newOperation(t.amount.startsWith("-") ? "EXPENSE" : "REVENUE", t)}>Créer une opération liée</button>
              <p>Pour un règlement déjà constaté ou une échéance d’emprunt, utilisez le formulaire correspondant, puis rapprochez son écriture.</p>
            </> : <button onClick={() => setEditor({ title: "Annuler le rapprochement", path: "/bank/transactions/" + t.id + "/unmatch", fields: [{ name: "reason", label: "Motif (au moins 5 caractères)" }] })}>Annuler le rapprochement</button>}
          </article>)}
          <button disabled={!bankOffset} onClick={() => setBankOffset(bankOffset - 50)}>Mouvements précédents</button><button disabled={transactions.length < 50} onClick={() => setBankOffset(bankOffset + 50)}>Mouvements suivants</button>
          {matchCandidates && <form onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); void action(async () => {
            await api("/bank/transactions/" + matchCandidates.transaction.id + "/match", "POST", { entry_line_id: Number(data.get("line")) }); setMatchCandidates(null); setRevision((v) => v + 1); setMessage("Rapprochement enregistré sans nouvelle écriture.");
          }); }}><h3>Rapprocher : {matchCandidates.transaction.label}</h3><p>Vérifiez la référence et la date : un montant égal ne suffit pas à identifier une opération.</p>
            {matchCandidates.lines.length ? <><label>Écriture de même montant<select name="line" required>{matchCandidates.lines.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}</select></label><button disabled={busy}>Confirmer le rapprochement</button></> : <p>Aucune écriture de même montant.</p>}
            <button type="button" onClick={() => setMatchCandidates(null)}>Annuler</button>
          </form>}
        </>}
      </>}
    </>}
  </section>;
}
