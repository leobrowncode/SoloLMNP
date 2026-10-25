import { useEffect, useState } from "react";
import { amount, cents, request, type Account, type Setup, type Entry } from "../api/ledger";
import { operationsRequest as api, type Property, type Bank, type Loan, type Operation, type BankTransaction, type ImportPreview, type OperationImportPreview, type LoanPaymentImportPreview, type Tenant } from "../api/operations";
import ReviewForm, { type Field } from "./ReviewForm";
import { buildPieceReference, defaultType, findType, typesFor } from "./operationTypes";
import "./ledger.css";

const kindLabel: Record<string, string> = {
  REVENUE: "Recette", EXPENSE: "Dépense", SETTLEMENT: "Règlement",
  LOAN_PAYMENT: "Échéance", LOAN_FUNDING: "Déblocage",
};
const TABS = ["Biens", "Banque", "Emprunts", "Transactions"] as const;

interface Editor {
  title: string;
  fields: Field[];
  path: string;
  retry?: boolean;
  fixed?: Record<string, unknown>;
  help?: string;
  sumInto?: { target: string; sources: string[] };
  derive?: (draft: Record<string, string>, changed: string) => Partial<Record<string, string>>;
}

export default function OperationsPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Biens");
  const [setup, setSetup] = useState<Setup | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [tenants, setTenants] = useState<Record<number, Tenant[]>>({});
  const [banks, setBanks] = useState<Bank[]>([]);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [operations, setOperations] = useState<Operation[]>([]);
  const [bankId, setBankId] = useState(0);
  const [transactions, setTransactions] = useState<BankTransaction[]>([]);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [csv, setCsv] = useState("");
  const [opCsv, setOpCsv] = useState("");
  const [opPreview, setOpPreview] = useState<OperationImportPreview | null>(null);
  const [opPropertyId, setOpPropertyId] = useState(0);
  const [opYearId, setOpYearId] = useState(0);
  const [loanCsv, setLoanCsv] = useState("");
  const [loanPreview, setLoanPreview] = useState<LoanPaymentImportPreview | null>(null);
  const [loanImportId, setLoanImportId] = useState(0);
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
    void Promise.all([
      request<Setup>("/setup"), request<Account[]>("/accounts"),
      api<Property[]>("/properties"), api<Bank[]>("/banks"), api<Loan[]>("/loans"),
      api<Operation[]>("?limit=50&offset=" + offset),
    ]).then(async ([s, a, p, b, l, o]) => {
      if (!active) return;
      const lists = await Promise.all(p.map((item) => api<Tenant[]>("/properties/" + item.id + "/tenants")));
      if (!active) return;
      setSetup(s); setAccounts(a); setProperties(p); setBanks(b); setLoans(l); setOperations(o);
      setTenants(Object.fromEntries(p.map((item, index) => [
        item.id,
        Array.isArray(lists[index]) ? lists[index] : [],
      ])));
      setBankId((current) => current || b[0]?.id || 0);
      setOpPropertyId((current) => current || p[0]?.id || 0);
      setOpYearId((current) => current || s.years.find((year) => year.status === "OPEN")?.id || 0);
      setLoanImportId((current) => current || l[0]?.id || 0);
      setLoaded(key);
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

  const choices = (items: { id: number; name: string }[]): [string, string][] =>
    items.map((item) => [String(item.id), item.name]);
  const propertyField: Field = {
    name: "property_id", label: "Bien", type: "number", group: "Contexte",
    choices: choices(properties),
  };
  const bankField: Field = {
    name: "bank_account_id", label: "Compte bancaire", type: "number", group: "Règlement",
    choices: choices(banks), value: String(bankId || ""),
  };
  const yearField: Field = {
    name: "fiscal_year_id", label: "Exercice de comptabilisation", type: "number", group: "Contexte",
    choices: setup?.years.filter((y) => y.status === "OPEN").map((y) => [String(y.id), String(y.year)]) ?? [],
  };
  const dateFields: Field[] = [
    { name: "date", label: "Date comptable", type: "date", group: "Contexte" },
    { name: "piece_reference", label: "Référence justificative", group: "Contexte" },
  ];
  const accountField = (name: string, label: string, prefix: string, value?: string, group = "Comptabilisation"): Field => ({
    name, label, value, group,
    choices: accounts.filter((a) => a.active && a.number.startsWith(prefix)).map((a) => [a.number, a.number + " · " + a.label]),
  });
  const settlementFields: Field[] = [
    yearField, ...dateFields, bankField,
  ];

  function newOperation(kind: "REVENUE" | "EXPENSE", transaction?: BankTransaction) {
    const initial = defaultType(kind);
    const date = transaction?.date ?? "";
    const bankRef = transaction?.external_reference?.trim() || "";
    const autoRef = buildPieceReference(initial.code, date, "");
    setEditor({
      title: kind === "REVENUE" ? "Enregistrer une recette" : "Enregistrer une dépense",
      path: "", retry: true,
      help: "Choisissez « Non réglé » si le paiement a lieu à une autre date, puis saisissez le règlement ensuite.",
      fixed: { kind, ...(transaction ? { bank_transaction_id: transaction.id } : {}) },
      derive: (draft) => {
        const type = findType(kind, draft.operation_type ?? "") ?? initial;
        return {
          accounting_account: type.account,
          piece_reference: buildPieceReference(type.code, draft.date ?? "", draft.counterparty ?? ""),
        };
      },
      fields: [
        {
          name: "operation_type", label: "Type d’opération", group: "Opération", local: true,
          choices: typesFor(kind).map((item) => [item.code, item.label] as [string, string]),
          value: initial.code,
          hint: "Préremplit le compte et la référence justificative.",
        },
        { ...propertyField, group: "Opération" },
        { ...yearField, group: "Opération" },
        {
          ...dateFields[0]!, value: date || undefined, group: "Opération",
          hint: "Date de l’écriture, dans l’exercice choisi.",
        },
        {
          name: "piece_date", label: "Date de la pièce", type: "date", value: date || undefined, group: "Opération",
          hint: "Date du justificatif. Elle peut différer.",
        },
        {
          name: "piece_reference", label: "Référence justificative", group: "Opération",
          value: bankRef || autoRef,
          hint: "Générée automatiquement — vous pouvez la modifier.",
        },
        { name: "description", label: "Description", value: transaction?.label, group: "Opération" },
        { name: "counterparty", label: kind === "REVENUE" ? "Locataire / client" : "Fournisseur", group: "Opération" },
        {
          name: "amount", label: "Montant intégral (€)", money: true, group: "Montants",
          value: transaction?.amount.replace("-", ""),
        },
        accountField(
          "accounting_account",
          "Compte de " + (kind === "REVENUE" ? "produit" : "charge"),
          kind === "REVENUE" ? "7" : "6",
          initial.account,
          "Montants",
        ),
        {
          ...bankField,
          group: "Règlement",
          label: "Règlement à cette même date",
          optional: !transaction,
          choices: transaction
            ? choices(banks.filter((b) => b.id === bankId))
            : [["", "Non réglé : compte client/fournisseur"], ...choices(banks)],
          value: transaction ? String(bankId) : "",
          hint: "Laissez « Non réglé » pour constater la créance ou la dette sans mouvement bancaire.",
        },
        ...(kind === "EXPENSE" ? [
          {
            name: "deductible_percentage",
            label: "Part déductible envisagée (%)",
            money: true, value: "100.00", group: "Fiscalité (indicatif)",
            hint: "Information à vérifier ; elle ne réduit jamais le montant comptable.",
          },
          {
            name: "fiscal_treatment", label: "Traitement fiscal envisagé", group: "Fiscalité (indicatif)",
            choices: [
              ["REQUIRES_REVIEW", "À vérifier"], ["DEDUCTIBLE", "Déductible"],
              ["PARTIAL", "Partiellement déductible"], ["NON_DEDUCTIBLE", "Non déductible"],
            ],
          } as Field,
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
    if (uniqueIds.length > 500) {
      throw new Error("Plus de 500 écritures candidates : affinez votre compte bancaire.");
    }
    const entries = await Promise.all(uniqueIds.map((id) => request<Entry>("/entries/" + id)));
    const lines = entries.flatMap((entry) => entry.lines.filter((line) =>
      line.account_number === number
      && (transaction.amount.startsWith("-")
        ? line.credit === transaction.amount.slice(1) && line.debit === "0.00"
        : line.debit === transaction.amount && line.credit === "0.00")
    ).map((line) => ({
      id: line.id,
      label: entry.entry_number + " · " + entry.accounting_date + " · " + entry.label,
    })));
    setMatchCandidates({ transaction, lines });
  }

  const openYears = setup?.years.filter((year) => year.status === "OPEN") ?? [];
  function occupants(id: number) {
    const rows = tenants[id];
    return Array.isArray(rows) ? rows : [];
  }
  return <section id="operations" className="ledger-page" aria-labelledby="operations-title">
    <h2 id="operations-title">Opérations et banque</h2>
    <p>Suivez l’ordre des onglets : bien, banque, emprunts, puis recettes et dépenses.</p>
    {error && <p role="alert" className="ledger-error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {!setup ? <p>Chargement…</p> : !setup.activity ? (
      <p>Initialisez votre activité et votre exercice dans <strong>Comptabilité</strong> avant de saisir vos opérations.</p>
    ) : <>
      <nav className="step-tabs" aria-label="Étapes des opérations">
        {TABS.map((name, index) => (
          <button
            key={name}
            type="button"
            aria-pressed={tab === name}
            onClick={() => { setTab(name); setEditor(null); setDetails(null); }}
          >
            <span className="step-index">{index + 1}</span> {name}
          </button>
        ))}
      </nav>

      {editor && (
        <ReviewForm
          key={JSON.stringify({ title: editor.title, path: editor.path })}
          title={editor.title}
          fields={editor.fields}
          help={editor.help}
          sumInto={editor.sumInto}
          derive={editor.derive}
          onSave={save}
          onCancel={() => setEditor(null)}
          retryId={editor.retry}
        />
      )}

      {tab === "Biens" && <>
        <p className="form-help">Ajoutez le logement avant les loyers. Terrain et bâtiment doivent égaler le prix. Les frais de notaire viennent en plus.</p>
        <button type="button" onClick={() => setEditor({
          title: "Ajouter un bien", path: "/properties",
          help: "Le terrain et le bâtiment doivent totaliser exactement le prix d’acquisition. Les frais restent à part.",
          derive: (draft, changed) => {
            if (!["lot_m2", "price_m2", "acquisition_price"].includes(changed)) return {};
            const area = Number(String(draft.lot_m2 ?? "").replace(",", "."));
            if (!Number.isFinite(area) || area <= 0) return {};
            try {
              const pricePerMeter = cents(draft.price_m2 || "0");
              const price = cents(draft.acquisition_price || "0");
              if (pricePerMeter <= 0n || price <= 0n) return {};
              const land = BigInt(Math.round(area * Number(pricePerMeter)));
              if (land <= 0n || land >= price) return {};
              return { land_value: amount(land), building_value: amount(price - land) };
            } catch {
              return {};
            }
          },
          fields: [
            { name: "name", label: "Nom du bien", group: "Identification" },
            { name: "address", label: "Adresse", group: "Identification" },
            { name: "acquisition_date", label: "Date d’acquisition", type: "date", group: "Dates" },
            { name: "rental_start_date", label: "Début de location", type: "date", optional: true, group: "Dates" },
            { name: "acquisition_price", label: "Prix d’acquisition (€)", money: true, group: "Valeurs" },
            { name: "acquisition_costs", label: "Frais de notaire et d’agence (€)", money: true, group: "Valeurs", hint: "Ajoutés plus tard à la base amortissable, pas au prix." },
            { name: "lot_m2", label: "Surface du terrain ou quote-part (m²)", local: true, group: "Terrain constaté", hint: "Pour un appartement, la quote-part de la parcelle." },
            { name: "price_m2", label: "Prix constaté au m² (€)", money: true, local: true, group: "Terrain constaté" },
            { name: "land_value", label: "Valeur du terrain (€)", money: true, group: "Valeurs", hint: "Non amortissable. Proposée si vous avez saisi une surface et un prix au m²." },
            { name: "building_value", label: "Valeur du bâtiment (€)", money: true, group: "Valeurs" },
          ],
        })}>Ajouter un bien</button>
        {properties.map((p) => (
          <article key={p.id} className="entry-card">
            <h3>{p.name}</h3>
            <p>Acquisition : {p.acquisition_price} € · Terrain : {p.land_value} € · Bâtiment : {p.building_value} €</p>
            <h4>Colocataires</h4>
            <ul>
              {occupants(p.id).map((tenant) => (
                <li key={tenant.id}>{tenant.name} · {tenant.monthly_rent} € / mois · depuis {tenant.entry_date}</li>
              ))}
            </ul>
            {occupants(p.id).length === 0 && <p>Aucun colocataire. Chaque locataire a son loyer.</p>}
            <button type="button" onClick={() => setEditor({
              title: "Colocataire — " + p.name,
              path: "/properties/" + p.id + "/tenants",
              help: "Un bail, un loyer. Les quittances de l’exercice se préparent ensuite, mois par mois, sans mouvement bancaire.",
              fields: [
                { name: "name", label: "Nom du locataire" },
                { name: "monthly_rent", label: "Loyer mensuel (€)", money: true },
                { name: "entry_date", label: "Entrée dans les lieux", type: "date" },
                { name: "exit_date", label: "Sortie, si elle est connue", type: "date", optional: true },
              ],
            })}>Ajouter un colocataire</button>
            <button type="button" disabled={!opYearId || !occupants(p.id).length} onClick={() => {
              void action(async () => {
                const result = await api<{ created: number; already: number }>("/properties/" + p.id + "/rents", "POST", { fiscal_year_id: opYearId });
                setMessage(result.created + " quittance(s) préparée(s), " + result.already + " déjà présentes. Elles restent à régler.");
                setRevision((value) => value + 1);
              });
            }}>Préparer les loyers de l’exercice</button>
          </article>
        ))}
      </>}

      {tab === "Banque" && <>
        <p className="form-help">Créez d’abord le compte bancaire, puis importez éventuellement un relevé CSV pour rapprocher.</p>
        <button type="button" onClick={() => setEditor({
          title: "Ajouter un compte bancaire", path: "/banks",
          fields: [
            { name: "name", label: "Nom du compte bancaire", group: "Banque" },
            accountField("account_number", "Compte comptable dédié", "512", undefined, "Banque"),
          ],
        })}>Ajouter un compte bancaire</button>
        {!!banks.length && <>
          <label className="toolbar-field">Banque sélectionnée
            <select value={bankId} onChange={(e) => {
              setBankId(Number(e.target.value)); setBankOffset(0); setPreview(null); setEditor(null); setMatchCandidates(null);
            }}>
              {banks.map((b) => <option key={b.id} value={b.id}>{b.name} · {b.account_number}</option>)}
            </select>
          </label>
          <details>
            <summary>Importer un relevé CSV</summary>
            <p>UTF-8, séparateur point-virgule, en-tête exact : <code>date;label;amount;reference</code>. L’import seul ne comptabilise rien.</p>
            <label>Fichier CSV (1 Mo maximum)<input type="file" accept=".csv,text/csv" onChange={(e) => {
              const file = e.target.files?.[0]; setPreview(null);
              if (file) void action(async () => {
                if (file.size > 1_000_000) throw new Error("Fichier trop volumineux.");
                setCsv(await file.text());
              });
            }} /></label>
            <label>Contenu CSV<textarea rows={6} value={csv} onChange={(e) => { setCsv(e.target.value); setPreview(null); }} /></label>
            <button type="button" disabled={busy || !csv} onClick={() => {
              void action(async () => setPreview(await api<ImportPreview>("/bank/preview", "POST", { bank_account_id: bankId, content: csv })));
            }}>Prévisualiser l’import</button>
            {preview && <>
              <p>{preview.count} mouvement(s) · {preview.rows.filter((r) => r.duplicate).length} déjà importé(s)</p>
              <div className="ledger-table"><table>
                <thead><tr><th>Date</th><th>Libellé</th><th>Montant</th><th>Déjà importé</th><th>Compte suggéré</th></tr></thead>
                <tbody>{preview.rows.map((row) => (
                  <tr key={row.reference}>
                    <td>{row.date}</td><td>{row.label}</td><td>{row.amount}</td>
                    <td>{row.duplicate ? "Oui" : "Non"}</td><td>{row.suggested_account || "À choisir"}</td>
                  </tr>
                ))}</tbody>
              </table></div>
              <button type="button" disabled={busy} onClick={() => {
                void action(async () => {
                  const result = await api<ImportPreview>("/bank/import", "POST", { bank_account_id: bankId, content: csv });
                  setMessage(result.imported + " mouvement(s) importé(s), en attente de rapprochement.");
                  setPreview(null); setRevision((v) => v + 1);
                });
              }}>Confirmer l’import des mouvements</button>
            </>}
          </details>
          {bankLoaded !== bankKey ? <p>Chargement du relevé…</p> : transactions.map((t) => (
            <article key={t.id} className="entry-card">
              <h3>{t.label} · {t.amount} €</h3>
              <p>{t.date} · {t.external_reference} · {t.matched_entry_id ? "Rapproché avec l’écriture #" + t.matched_entry_id : "À rapprocher"}</p>
              {!t.matched_entry_id ? <>
                <button type="button" disabled={busy} onClick={() => { void action(() => findCandidates(t)); }}>Rapprocher une écriture existante</button>
                <button type="button" disabled={!properties.length} onClick={() => newOperation(t.amount.startsWith("-") ? "EXPENSE" : "REVENUE", t)}>Créer une opération liée</button>
              </> : (
                <button type="button" onClick={() => setEditor({
                  title: "Annuler le rapprochement", path: "/bank/transactions/" + t.id + "/unmatch",
                  fields: [{ name: "reason", label: "Motif (au moins 5 caractères)", group: "Annulation" }],
                })}>Annuler le rapprochement</button>
              )}
            </article>
          ))}
          <div className="form-actions">
            <button type="button" disabled={!bankOffset} onClick={() => setBankOffset(bankOffset - 50)}>Mouvements précédents</button>
            <button type="button" disabled={transactions.length < 50} onClick={() => setBankOffset(bankOffset + 50)}>Mouvements suivants</button>
          </div>
          {matchCandidates && <form className="entry-editor" onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            void action(async () => {
              await api("/bank/transactions/" + matchCandidates.transaction.id + "/match", "POST", { entry_line_id: Number(data.get("line")) });
              setMatchCandidates(null); setRevision((v) => v + 1);
              setMessage("Rapprochement enregistré sans nouvelle écriture.");
            });
          }}>
            <h3>Rapprocher : {matchCandidates.transaction.label}</h3>
            <p>Vérifiez la référence et la date : un montant égal ne suffit pas.</p>
            {matchCandidates.lines.length ? <>
              <label>Écriture de même montant
                <select name="line" required>{matchCandidates.lines.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}</select>
              </label>
              <button type="submit" disabled={busy}>Confirmer le rapprochement</button>
            </> : <p>Aucune écriture de même montant.</p>}
            <button type="button" onClick={() => setMatchCandidates(null)}>Annuler</button>
          </form>}
        </>}
      </>}

      {tab === "Emprunts" && <>
        <p className="form-help">Chaque ligne de crédit = un emprunt SoloLMNP avec son propre compte 164. Exemple : 15&nbsp;000 € et 195&nbsp;000 € → deux emprunts. Un compte 164 libre est attribué automatiquement si besoin.</p>
        <button type="button" disabled={!properties.length} onClick={() => {
          const used = new Set(loans.map((loan) => loan.principal_account));
          const free164 = accounts
            .filter((a) => a.active && a.number.startsWith("164") && !used.has(a.number))
            .map((a) => [a.number, a.number + " · " + a.label] as [string, string]);
          setEditor({
          title: "Ajouter un emprunt", path: "/loans",
          help: "Pour un crédit à deux lignes, créez deux emprunts séparés (ex. 15 000 € puis 195 000 €). Laissez l’attribution automatique du compte 164 si 164000 est déjà pris.",
          fields: [
            propertyField,
            { name: "lender", label: "Prêteur", group: "Emprunt" },
            { name: "start_date", label: "Début de l’emprunt", type: "date", group: "Emprunt" },
            { name: "initial_principal", label: "Capital de cette ligne (€)", money: true, group: "Conditions", hint: "Montant d’une seule ligne du crédit, pas le total du contrat." },
            { name: "interest_rate", label: "Taux annuel (%)", money: true, group: "Conditions", hint: "Informatif." },
            { name: "duration_months", label: "Durée en mois", type: "number", group: "Conditions" },
            { name: "monthly_payment", label: "Mensualité contractuelle (€)", money: true, value: "0.00", group: "Conditions", hint: "Informatif." },
            { name: "monthly_insurance", label: "Assurance mensuelle (€)", money: true, value: "0.00", group: "Conditions", hint: "Informatif." },
            {
              name: "principal_account",
              label: "Compte de capital dédié",
              group: "Comptabilisation",
              optional: true,
              choices: [["", "Attribution automatique d’un compte 164 libre"], ...free164],
              value: "",
              hint: free164.length
                ? "Les comptes déjà utilisés par un autre emprunt sont masqués."
                : "164000 est déjà pris : un compte 164001 (ou suivant) sera créé à l’enregistrement.",
            },
          ],
        });
        }}>Ajouter un emprunt</button>
        {!properties.length && <p>Ajoutez d’abord un bien.</p>}
        {!banks.length && <p>Ajoutez un compte bancaire avant déblocage ou échéance.</p>}
        {loans.map((l) => (
          <article className="entry-card" key={l.id}>
            <h3>{l.lender}</h3>
            <p>Capital initial : {l.initial_principal} € · Solde comptable : {l.remaining_principal} € · Mensualité : {l.monthly_payment} € + assurance {l.monthly_insurance} € · Compte {l.principal_account}</p>
            <button type="button" disabled={!banks.length} onClick={() => setEditor({
              title: "Déblocage initial : " + l.lender,
              path: "/loans/" + l.id + "/fund",
              retry: true,
              help: "Le montant doit égaler le capital initial. Un seul déblocage non extourné est autorisé.",
              fields: [
                ...settlementFields,
                { name: "amount", label: "Montant débloqué (€)", money: true, value: l.initial_principal, group: "Montant" },
              ],
            })}>Enregistrer le déblocage</button>
            <button type="button" disabled={!banks.length} onClick={() => {
              const rate = BigInt(l.interest_rate_basis_points ?? 0);
              const remaining = cents(l.remaining_principal);
              const interest = remaining * rate / 120000n;
              const insurance = cents(l.monthly_insurance || "0");
              const payment = cents(l.monthly_payment || "0");
              let principal = payment > 0n ? payment - interest - insurance : 0n;
              if (principal < 0n) principal = 0n;
              if (principal > remaining) principal = remaining;
              setEditor({
              title: "Échéance : " + l.lender,
              path: "/loans/" + l.id + "/payments",
              retry: true,
              help: "Intérêts proposés à partir du taux et du capital restant. Vérifiez-les sur l’échéancier de la banque. Ne ressaisissez pas ces intérêts comme une dépense.",
              sumInto: {
                target: "amount",
                sources: ["principal", "interest", "insurance", "other_costs"],
              },
              fields: [
                ...settlementFields,
                { name: "principal", label: "Capital remboursé (€)", money: true, value: amount(principal), group: "Ventilation de l’échéance", hint: "Ligne 1 — compte 164" },
                { name: "interest", label: "Intérêts (€)", money: true, value: amount(interest), group: "Ventilation de l’échéance", hint: "Ligne 2 — compte 661" },
                { name: "insurance", label: "Assurance (€)", money: true, value: amount(insurance), group: "Ventilation de l’échéance", hint: "Ligne 3 — compte 616" },
                { name: "other_costs", label: "Autres frais (€)", money: true, group: "Ventilation de l’échéance", hint: "Ligne 4 — compte 627" },
              ],
            });
            }}>Saisir une échéance</button>
          </article>
        ))}
        {!!loans.length && !!banks.length && !!openYears.length && <details>
          <summary>Importer les échéances depuis Google Sheets ou un CSV</summary>
          <p>Collez l’en-tête et les lignes d’un seul prêt. Colonnes reconnues : <code>Prêt;Rang;Date;Capital (€);Intérêts (€);Assurance banque (€);Assurance externe à compléter (€);Total banque (€)</code>. Seules les échéances de l’exercice déjà arrivées à leur date seront proposées.</p>
          <p>L’assurance externe prélevée séparément reste une dépense <code>ASS</code> : ne l’incluez pas dans le total banque.</p>
          <label className="toolbar-field">Emprunt
            <select value={loanImportId} onChange={(e) => {
              setLoanImportId(Number(e.target.value)); setLoanPreview(null);
            }}>
              {loans.map((loan) => (
                <option key={loan.id} value={loan.id}>
                  {loan.lender} · {loan.initial_principal} € · {loan.principal_account}
                </option>
              ))}
            </select>
          </label>
          <label className="toolbar-field">Exercice
            <select value={opYearId} onChange={(e) => {
              setOpYearId(Number(e.target.value)); setLoanPreview(null);
            }}>
              {openYears.map((year) => (
                <option key={year.id} value={year.id}>{year.year}</option>
              ))}
            </select>
          </label>
          <label className="toolbar-field">Compte bancaire
            <select value={bankId} onChange={(e) => {
              setBankId(Number(e.target.value)); setBankOffset(0); setLoanPreview(null);
            }}>
              {banks.map((bank) => (
                <option key={bank.id} value={bank.id}>{bank.name} · {bank.account_number}</option>
              ))}
            </select>
          </label>
          <label>Fichier CSV Google Sheets ou à point-virgule (1 Mo maximum)<input type="file" accept=".csv,text/csv" onChange={(e) => {
            const file = e.target.files?.[0]; setLoanPreview(null);
            if (file) void action(async () => {
              if (file.size > 1_000_000) throw new Error("Fichier trop volumineux.");
              setLoanCsv(await file.text());
            });
          }} /></label>
          <label>Lignes du tableau d’amortissement<textarea rows={8} value={loanCsv} onChange={(e) => {
            setLoanCsv(e.target.value); setLoanPreview(null);
          }} /></label>
          <button type="button" disabled={busy || !loanCsv || !loanImportId || !opYearId || !bankId} onClick={() => {
            void action(async () => setLoanPreview(await api<LoanPaymentImportPreview>(
              "/loans/" + loanImportId + "/payments/import/preview",
              "POST",
              { fiscal_year_id: opYearId, bank_account_id: bankId, content: loanCsv },
            )));
          }}>Prévisualiser les échéances</button>
          {loanPreview && <>
            <p>
              {loanPreview.count} échéance(s) retenue(s) sur {loanPreview.source_count}
              {" · "}{loanPreview.outside_year} hors exercice
              {" · "}{loanPreview.future} future(s)
              {" · "}{loanPreview.rows.filter((row) => row.duplicate).length} déjà comptabilisée(s)
              {loanPreview.loan_reference ? " · prêt " + loanPreview.loan_reference : ""}
            </p>
            {loanPreview.rows.length ? <div className="ledger-table"><table>
              <thead><tr><th>Date</th><th>Rang</th><th>Capital</th><th>Intérêts</th><th>Assurance banque</th><th>Autres frais</th><th>Total banque</th><th>État</th></tr></thead>
              <tbody>{loanPreview.rows.map((row) => (
                <tr key={row.date}>
                  <td>{row.date}</td><td>{row.rank || "—"}</td><td>{row.principal} €</td>
                  <td>{row.interest} €</td><td>{row.insurance} €</td>
                  <td>{row.other_costs} €</td><td>{row.amount} €</td>
                  <td>{row.duplicate ? "Déjà comptabilisée" : "À comptabiliser"}</td>
                </tr>
              ))}</tbody>
            </table></div> : <p>Aucune échéance arrivée à sa date pour cet exercice.</p>}
            <button type="button" disabled={busy || !loanPreview.rows.some((row) => !row.duplicate)} onClick={() => {
              void action(async () => {
                const result = await api<LoanPaymentImportPreview>(
                  "/loans/" + loanImportId + "/payments/import",
                  "POST",
                  { fiscal_year_id: opYearId, bank_account_id: bankId, content: loanCsv },
                );
                setMessage(result.imported + " échéance(s) comptabilisée(s). Rapprochez ensuite le relevé bancaire.");
                setLoanPreview(null); setRevision((value) => value + 1);
              });
            }}>Comptabiliser les échéances</button>
          </>}
        </details>}
      </>}

      {tab === "Transactions" && <>
        <p className="form-help">Enregistrez les loyers et charges. La part déductible ne change pas l’écriture : elle est proposée ensuite dans les réintégrations de la liasse. Ne saisissez pas les intérêts déjà ventilés dans une échéance d’emprunt.</p>
        <details>
          <summary>Importer depuis Google Sheets ou un CSV</summary>
          <p>Copiez les lignes du Google Sheet de saisie (en-tête compris) et collez-les ci-dessous, ou chargez un CSV à point-virgule. Colonnes : <code>kind date piece_date type counterparty amount description piece_reference source_file</code>, plus <code>paid</code> facultative. <code>kind</code> : Recette ou Dépense ; dates JJ/MM/AAAA ou AAAA-MM-JJ ; <code>paid</code> = oui pour une ligne déjà payée sur le compte choisi, sinon elle reste à régler. Le traitement fiscal reste à vérifier. Une référence déjà comptabilisée est ignorée ; la même référence avec un autre montant est refusée.</p>
          {!!properties.length && !!openYears.length && <>
            <label className="toolbar-field">Bien
              <select value={opPropertyId} onChange={(e) => { setOpPropertyId(Number(e.target.value)); setOpPreview(null); }}>
                {properties.map((property) => <option key={property.id} value={property.id}>{property.name}</option>)}
              </select>
            </label>
            <label className="toolbar-field">Exercice
              <select value={opYearId} onChange={(e) => { setOpYearId(Number(e.target.value)); setOpPreview(null); }}>
                {openYears.map((year) => (
                  <option key={year.id} value={year.id}>{year.year}</option>
                ))}
              </select>
            </label>
            {!!banks.length && <label className="toolbar-field">Compte des lignes payées
              <select value={bankId} onChange={(e) => { setBankId(Number(e.target.value)); setOpPreview(null); }}>
                {banks.map((b) => <option key={b.id} value={b.id}>{b.name} ({b.account_number})</option>)}
              </select>
            </label>}
          </>}
          <label>Fichier CSV (1 Mo maximum)<input type="file" accept=".csv,text/csv" onChange={(e) => {
            const file = e.target.files?.[0]; setOpPreview(null);
            if (file) void action(async () => {
              if (file.size > 1_000_000) throw new Error("Fichier trop volumineux.");
              setOpCsv(await file.text());
            });
          }} /></label>
          <label>Lignes collées ou contenu CSV<textarea rows={6} value={opCsv} onChange={(e) => { setOpCsv(e.target.value); setOpPreview(null); }} /></label>
          <button type="button" disabled={busy || !opCsv || !opPropertyId || !opYearId} onClick={() => {
            void action(async () => setOpPreview(await api<OperationImportPreview>("/import/preview", "POST", {
              property_id: opPropertyId, fiscal_year_id: opYearId, content: opCsv, bank_account_id: bankId || null,
            })));
          }}>Prévisualiser les justificatifs</button>
          {opPreview && <>
            <p>{opPreview.count} opération(s) · {opPreview.rows.filter((row) => row.duplicate).length} déjà importée(s)</p>
            <div className="ledger-table"><table>
              <thead><tr><th>Date</th><th>Nature</th><th>Tiers</th><th>Montant</th><th>Payée</th><th>Référence</th><th>Fichier</th><th>Déjà importée</th></tr></thead>
              <tbody>{opPreview.rows.map((row) => (
                <tr key={row.piece_reference}>
                  <td>{row.date}</td>
                  <td>{kindLabel[row.kind] || row.kind} · {row.type} · {row.accounting_account}</td>
                  <td>{row.counterparty}</td>
                  <td>{row.amount}</td>
                  <td>{row.paid ? "Oui" : "À régler"}</td>
                  <td>{row.piece_reference}</td>
                  <td>{row.source_file || "—"}</td>
                  <td>{row.duplicate ? "Oui" : "Non"}</td>
                </tr>
              ))}</tbody>
            </table></div>
            <button type="button" disabled={busy || opPreview.rows.every((row) => row.duplicate)} onClick={() => {
              void action(async () => {
                const result = await api<OperationImportPreview>("/import", "POST", {
                  property_id: opPropertyId, fiscal_year_id: opYearId, content: opCsv, bank_account_id: bankId || null,
                });
                setMessage(result.imported + " opération(s) comptabilisée(s). Lignes non payées à régler ; traitement fiscal à vérifier.");
                setOpPreview(null); setRevision((value) => value + 1);
              });
            }}>Comptabiliser les justificatifs</button>
          </>}
        </details>
        <div className="form-actions">
          <button type="button" disabled={!properties.length || !setup.years.some((y) => y.status === "OPEN")} onClick={() => newOperation("REVENUE")}>Nouvelle recette</button>
          <button type="button" disabled={!properties.length || !setup.years.some((y) => y.status === "OPEN")} onClick={() => newOperation("EXPENSE")}>Nouvelle dépense</button>
        </div>
        {!properties.length && <p>Ajoutez d’abord un bien dans l’onglet Biens.</p>}
        {loaded !== key ? <p>Chargement des opérations…</p> : operations.map((row) => (
          <article key={row.id} className="entry-card">
            <h3>{kindLabel[row.kind]} · {row.description} · {row.amount} €</h3>
            <p>{row.date} · {row.counterparty} · {row.status === "REVERSED" ? "Extournée" : "Comptabilisée"}{row.remaining_to_settle !== null && " · Reste à régler : " + row.remaining_to_settle + " €"}</p>
            {row.kind === "LOAN_PAYMENT" && (
              <p>Capital {row.principal} € · Intérêts {row.interest} € · Assurance {row.insurance} € · Frais {row.other_costs} €</p>
            )}
            <button type="button" onClick={() => { void action(async () => setDetails(await request<Entry>("/entries/" + row.accounting_entry_id))); }}>Voir l’écriture</button>
            {row.status !== "REVERSED" && row.remaining_to_settle && row.remaining_to_settle !== "0.00" && (
              <button type="button" disabled={!banks.length} onClick={() => setEditor({
                title: "Régler : " + row.description,
                path: "/" + row.id + "/settle",
                retry: true,
                fields: [
                  ...settlementFields,
                  { name: "amount", label: "Montant (€)", money: true, value: row.remaining_to_settle!, group: "Montant" },
                ],
              })}>Enregistrer un règlement</button>
            )}
            {row.status !== "REVERSED" && (
              <button type="button" onClick={() => setEditor({
                title: "Extourner : " + row.description,
                path: "/" + row.id + "/reverse",
                fields: [
                  { name: "accounting_date", label: "Date d’extourne", type: "date", group: "Extourne" },
                  { name: "piece_reference", label: "Pièce d’extourne", group: "Extourne" },
                  { name: "reason", label: "Motif (au moins 5 caractères)", group: "Extourne" },
                ],
              })}>Extourner l’opération</button>
            )}
          </article>
        ))}
        <div className="form-actions">
          <button type="button" disabled={!offset} onClick={() => setOffset(offset - 50)}>Opérations précédentes</button>
          <button type="button" disabled={operations.length < 50} onClick={() => setOffset(offset + 50)}>Opérations suivantes</button>
        </div>
      </>}

      {details && (
        <div className="ledger-table">
          <h3>{details.entry_number} · {details.label}</h3>
          <table>
            <thead><tr><th>Compte</th><th>Libellé</th><th>Débit</th><th>Crédit</th></tr></thead>
            <tbody>{details.lines.map((line, i) => (
              <tr key={i}><td>{line.account_number}</td><td>{line.label}</td><td>{line.debit}</td><td>{line.credit}</td></tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </>}
  </section>;
}
