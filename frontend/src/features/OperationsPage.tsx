import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { amount, cents, request, type Account, type Setup, type Entry, RequestError } from "../api/ledger";
import {
  activityCause, bankCause, describedBy, listed,
  openYearCauses, operationEntryCauses, propertyCause, rentCauses,
} from "./actionCauses";
import CsvImportAssistant from "./CsvImportAssistant";
import ApiErrorAlert from "./ApiErrorAlert";
import GlossaryTip from "./GlossaryTip";
import PrerequisiteList from "./PrerequisiteList";
import ScreenStatus from "./ScreenStatus";
import {
  beginLoad, defer, failLoad, finishLoad, idleView, showsData, showsLoading, toApiError, type ScreenView,
} from "./screenState";
import { operationsRequest as api, type Property, type Bank, type Loan, type Operation, type BankTransaction, type Tenant } from "../api/operations";
import {
  DEFAULT_OPERATIONS_TAB,
  OPERATIONS_TABS,
  operationsPath,
  operationsTabFromSlug,
  type OperationsTab,
} from "../routing/paths";
import { useUnsavedGuard } from "../routing/useUnsavedGuard";
import ReviewForm, { type Field } from "./ReviewForm";
import { GLOSSARY } from "./glossary";
import { SaveNoticeHost } from "./LocalFeedback";
import { useSaveNotice } from "./localFeedback";
import { operationSaveNotice } from "./operationSave";
import MutationStatus from "./MutationStatus";
import { useMutation } from "./useMutation";
import {
  PLAN_HELP, RECORD_HELP, correctionMessage, locked, readInvalidation,
} from "./correction";
import { buildPieceReference, defaultType, findType, typesFor } from "./operationTypes";
import { enumChoices, enumLabel, formatEuros, formatIsoDate } from "../lib/format";
import FrenchForm from "../lib/FrenchForm";
import "./ledger.css";
import FitSelect from "../lib/FitSelect";
import { PageAnchors } from "../lib/PageSection";
import { ResponsiveTable } from "../lib/ResponsiveTable";

interface Editor {
  title: string;
  fields: Field[];
  path: string;
  method?: "POST" | "PATCH";
  retry?: boolean;
  fixed?: Record<string, unknown>;
  help?: string;
  sumInto?: { target: string; sources: string[] };
  derive?: (draft: Record<string, string>, changed: string) => Partial<Record<string, string>>;
}

export default function OperationsPage() {
  const { tab: tabSlug } = useParams();
  const navigate = useNavigate();
  const resolvedTab = operationsTabFromSlug(tabSlug);
  const tab: OperationsTab = resolvedTab ?? DEFAULT_OPERATIONS_TAB;
  const [setup, setSetup] = useState<Setup | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [tenants, setTenants] = useState<Record<number, Tenant[]>>({});
  const [banks, setBanks] = useState<Bank[]>([]);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [operations, setOperations] = useState<Operation[]>([]);
  const [bankId, setBankId] = useState(0);
  const [transactions, setTransactions] = useState<BankTransaction[]>([]);
  const [opPropertyId, setOpPropertyId] = useState(0);
  const [opYearId, setOpYearId] = useState(0);
  const [loanImportId, setLoanImportId] = useState(0);
  const [editor, setEditor] = useState<Editor | null>(null);
  useUnsavedGuard(!!editor);

  function openTab(next: OperationsTab) {
    navigate(operationsPath(next));
    setEditor(null);
    setDetails(null);
  }

  const [error, setError] = useState("");
  const [apiError, setApiError] = useState<RequestError | null>(null);
  const [bundleView, setBundleView] = useState<ScreenView<{ key: string }>>(() => beginLoad(idleView(), false));
  const [bankView, setBankView] = useState<ScreenView<{ query: string }>>(idleView());
  const { notice, show, dismiss } = useSaveNotice();
  const [revision, setRevision] = useState(0);
  const { busy, step, run } = useMutation();
  const [offset, setOffset] = useState(0);
  const [bankOffset, setBankOffset] = useState(0);
  const [details, setDetails] = useState<Entry | null>(null);
  const [matchCandidates, setMatchCandidates] = useState<{ transaction: BankTransaction; lines: { id: number; label: string }[] } | null>(null);
  const bundleKey = String(offset);
  const bankQuery = JSON.stringify([bankId, bankOffset]);

  useEffect(() => {
    let active = true;
    defer(() => {
      if (!active) return;
      setBundleView((current) => beginLoad(current, current.data?.key === bundleKey));
    });
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
      setBundleView(finishLoad({ key: bundleKey }));
    }).catch((reason: unknown) => {
      if (active) setBundleView((current) => failLoad(current, toApiError(reason), current.data?.key === bundleKey));
    });
    return () => { active = false; };
  }, [revision, offset, bundleKey]);

  useEffect(() => {
    let active = true;
    if (!bankId) {
      defer(() => {
        if (active) setBankView(idleView());
      });
      return () => { active = false; };
    }
    defer(() => {
      if (!active) return;
      setBankView((current) => beginLoad(current, current.data?.query === bankQuery));
    });
    void api<BankTransaction[]>("/bank/transactions?bank_account_id=" + bankId + "&limit=50&offset=" + bankOffset).then((items) => {
      if (!active) return;
      setTransactions(items);
      setBankView(finishLoad({ query: bankQuery }, () => items.length === 0));
    }).catch((reason: unknown) => {
      if (active) setBankView((current) => failLoad(current, toApiError(reason), current.data?.query === bankQuery));
    });
    return () => { active = false; };
  }, [bankId, revision, bankOffset, bankQuery]);

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
            choices: enumChoices("fiscalTreatment"),
          } as Field,
        ] : []),
      ],
    });
  }

  async function save(data: Record<string, unknown>) {
    await run(async (report) => {
      if (!editor) return;
      report("Enregistrement…");
      setError(""); setApiError(null); dismiss();
      const savedEditor = editor;
      const result = await api<Record<string, unknown>>(savedEditor.path, savedEditor.method ?? "POST", { ...data, ...savedEditor.fixed });
      const invalidation = readInvalidation(result.invalidation);
      setEditor(null); setDetails(null);
      show(operationSaveNotice({
        path: savedEditor.path,
        method: savedEditor.method,
        title: savedEditor.title,
        fixed: savedEditor.fixed,
        data,
        result,
        detail: invalidation ? correctionMessage(invalidation) : undefined,
      }));
      setRevision((v) => v + 1);
    });
  }

  async function action(fn: () => Promise<unknown>, label = "Opération en cours…") {
    await run(async (report) => {
      report(label);
      setError(""); setApiError(null); dismiss();
      try { await fn(); } catch (e) {
        if (e instanceof RequestError) {
          setApiError(e);
          setError("");
        } else {
          setApiError(null);
          setError(e instanceof Error ? e.message : "Service indisponible.");
        }
      }
    });
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

  const years = setup?.years ?? [];
  const openYears = years.filter((year) => year.status === "OPEN");
  const entryCauses = operationEntryCauses(properties.length, years);
  const entryCauseId = "operation-entry-causes";
  const bankCauses = listed(bankCause(banks.length));
  const bankCauseId = "operation-bank-causes";
  const loanCauses = listed(propertyCause(properties.length));
  const loanCauseId = "loan-create-causes";
  const activityCauses = listed(activityCause(Boolean(setup?.activity)));
  const loanForImport = loans.find((loan) => loan.id === loanImportId);
  function occupants(id: number) {
    const rows = tenants[id];
    return Array.isArray(rows) ? rows : [];
  }
  function reasonField(): Field {
    return { name: "reason", label: "Motif de la correction (au moins 5 caractères)", group: "Motif" };
  }
  function openProperty(row: Property) {
    const financial = !locked(row.correction, "financial");
    const fields: Field[] = [
      { name: "name", label: "Nom du bien", value: row.name, group: "Identification" },
      { name: "address", label: "Adresse", value: row.address ?? "", group: "Identification" },
      { name: "rental_start_date", label: "Début de location", type: "date", optional: true, value: row.rental_start_date ?? "", group: "Dates" },
      { name: "notes", label: "Notes", optional: true, value: row.notes ?? "", group: "Identification" },
    ];
    if (financial) {
      fields.push(
        { name: "acquisition_date", label: "Date d’acquisition", type: "date", value: row.acquisition_date ?? "", group: "Valeurs" },
        { name: "acquisition_price", label: "Prix d’acquisition (€)", money: true, value: row.acquisition_price, group: "Valeurs" },
        { name: "acquisition_costs", label: "Frais de notaire et d’agence (€)", money: true, value: row.acquisition_costs ?? "0.00", group: "Valeurs" },
        { name: "land_value", label: "Valeur du terrain (€)", money: true, value: row.land_value, group: "Valeurs" },
        { name: "building_value", label: "Valeur du bâtiment (€)", money: true, value: row.building_value, group: "Valeurs" },
      );
    }
    fields.push(reasonField());
    setEditor({
      title: `Modifier ${row.name}`,
      path: `/properties/${row.id}`,
      method: "PATCH",
      help: financial ? PLAN_HELP : RECORD_HELP,
      fields,
    });
  }
  function openTenant(tenant: Tenant) {
    const identity = !locked(tenant.correction, "identity");
    const fields: Field[] = [];
    if (identity) {
      fields.push(
        { name: "name", label: "Nom du locataire", value: tenant.name },
        { name: "monthly_rent", label: "Loyer mensuel (€)", money: true, value: tenant.monthly_rent },
        { name: "entry_date", label: "Entrée dans les lieux", type: "date", value: tenant.entry_date },
      );
    }
    fields.push(
      { name: "exit_date", label: "Sortie, si elle est connue", type: "date", optional: true, value: tenant.exit_date ?? "" },
      reasonField(),
    );
    setEditor({
      title: identity ? `Modifier ${tenant.name}` : `Préciser la sortie de ${tenant.name}`,
      path: `/properties/${tenant.property_id}/tenants/${tenant.id}`,
      method: "PATCH",
      help: RECORD_HELP,
      fields,
    });
  }
  function openBank(row: Bank) {
    const numberLocked = locked(row.correction, "account_number");
    const fields: Field[] = [
      { name: "name", label: "Nom du compte bancaire", value: row.name, group: "Banque" },
    ];
    if (!numberLocked) {
      fields.push(accountField("account_number", "Compte comptable dédié", "512", row.account_number, "Banque"));
    }
    fields.push(reasonField());
    setEditor({
      title: `Modifier ${row.name}`,
      path: `/banks/${row.id}`,
      method: "PATCH",
      help: RECORD_HELP,
      fields,
    });
  }
  function openLoan(row: Loan) {
    const identity = !locked(row.correction, "identity");
    const rate = row.interest_rate ?? (Number(row.interest_rate_basis_points ?? 0) / 100).toFixed(2);
    const fields: Field[] = [];
    if (identity) {
      fields.push(
        { name: "start_date", label: "Début de l’emprunt", type: "date", value: row.start_date ?? "", group: "Emprunt" },
        { name: "initial_principal", label: "Capital de cette ligne (€)", money: true, value: row.initial_principal, group: "Conditions" },
      );
    }
    fields.push(
      { name: "lender", label: "Prêteur", value: row.lender, group: "Emprunt" },
      { name: "interest_rate", label: "Taux annuel (%)", money: true, value: rate, group: "Conditions" },
      { name: "duration_months", label: "Durée en mois", type: "number", value: row.duration_months == null ? "" : String(row.duration_months), group: "Conditions" },
      { name: "monthly_payment", label: "Mensualité contractuelle (€)", money: true, value: row.monthly_payment, group: "Conditions" },
      { name: "monthly_insurance", label: "Assurance mensuelle (€)", money: true, value: row.monthly_insurance, group: "Conditions" },
      { name: "notes", label: "Notes", optional: true, value: row.notes ?? "", group: "Emprunt" },
      reasonField(),
    );
    setEditor({
      title: `Modifier ${row.lender}`,
      path: `/loans/${row.id}`,
      method: "PATCH",
      help: PLAN_HELP,
      fields,
    });
  }
  return <>
    {tabSlug && !resolvedTab && <Navigate to={operationsPath(DEFAULT_OPERATIONS_TAB)} replace />}
    <section id="operations" className="ledger-page" aria-labelledby="operations-title" data-screen-phase={bundleView.phase}>
    <h2 id="operations-title">Opérations et banque</h2>
    <p>Suivez l’ordre des onglets : bien, banque, emprunts, puis recettes et dépenses.</p>
    <PageAnchors
      label="Sections des opérations"
      links={
        tab === "Biens" ? [
          { href: "#biens-saisie", label: "Biens" },
          { href: "#ajouter-bien", label: "Ajouter un bien" },
        ] : tab === "Banque" ? [
          { href: "#banque-saisie", label: "Banque" },
          { href: "#ajouter-banque", label: "Ajouter une banque" },
          { href: "#import-import-releve", label: "Import du relevé" },
        ] : tab === "Emprunts" ? [
          { href: "#emprunts-saisie", label: "Emprunts" },
          { href: "#ajouter-emprunt", label: "Ajouter un emprunt" },
          { href: "#import-import-echeances", label: "Import des échéances" },
        ] : [
          { href: "#transactions-saisie", label: "Transactions" },
          { href: "#import-import-operations", label: "Import CSV" },
        ]
      }
    />
    <MutationStatus step={step} />
    {apiError && <ApiErrorAlert detail={apiError.detail} />}
    {error && !apiError && <p role="alert" className="ledger-error">{error}</p>}
    <ScreenStatus
      state={bundleView}
      onRetry={() => setRevision((value) => value + 1)}
      loading={!setup ? <p>Chargement…</p> : null}
    />
    {bundleView.phase === "loaded" && setup && !setup.activity && (
      <PrerequisiteList id="operations-activity" causes={activityCauses} intro="Initialisez votre activité avant de saisir des opérations :" />
    )}
    {showsData(bundleView) && setup?.activity && <>
      <nav className="step-tabs" aria-label="Étapes des opérations">
        {OPERATIONS_TABS.map((name, index) => (
          <button
            key={name}
            type="button"
            aria-pressed={tab === name}
            onClick={() => openTab(name)}
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
          locked={busy}
        />
      )}

      {tab === "Biens" && <div id="biens-saisie">
        <SaveNoticeHost place="biens-saisie" notice={notice} onDismiss={dismiss} />
        <p className="form-help">Ajoutez le logement avant les loyers. Terrain et bâtiment doivent égaler le prix. Les frais de notaire viennent en plus.</p>
        <button id="ajouter-bien" type="button" onClick={() => setEditor({
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
          <article key={p.id} id={`bien-${p.id}`} className="entry-card">
            <h3>{p.name}</h3>
            <p>Acquisition : {formatEuros(p.acquisition_price)} · Terrain : {formatEuros(p.land_value)} · Bâtiment : {formatEuros(p.building_value)}</p>
            {p.correction?.locks.map((lock) => <p className="form-help" key={lock.code}>{lock.message}</p>)}
            <div className="entry-actions">
              <button type="button" onClick={() => openProperty(p)}>Modifier {p.name}</button>
            </div>
            <h3 id={`colocataires-${p.id}`} tabIndex={-1}>Colocataires</h3>
            <ul>
              {occupants(p.id).map((tenant) => (
                <li key={tenant.id}>
                  {tenant.name} · {formatEuros(tenant.monthly_rent)} / mois · depuis {formatIsoDate(tenant.entry_date)}
                  {tenant.exit_date ? ` · sortie ${tenant.exit_date}` : ""}
                  {tenant.correction?.locks.map((lock) => <p className="form-help" key={lock.code}>{lock.message}</p>)}
                  <div className="entry-actions">
                    <button type="button" onClick={() => openTenant(tenant)}>
                      {locked(tenant.correction, "identity") ? `Préciser la sortie de ${tenant.name}` : `Modifier ${tenant.name}`}
                    </button>
                  </div>
                </li>
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
            <button type="button" disabled={rentCauses(p.id, occupants(p.id).length, years).length > 0} aria-describedby={describedBy(`rents-${p.id}`, rentCauses(p.id, occupants(p.id).length, years))} onClick={() => {
              void action(async () => {
                const result = await api<{ created: number; already: number }>("/properties/" + p.id + "/rents", "POST", { fiscal_year_id: opYearId });
                show({
                  kind: "Quittance",
                  name: p.name,
                  action: result.created ? "préparée" : "déjà préparée",
                  targetId: "biens-saisie",
                  highlightId: `bien-${p.id}`,
                  detail: result.created + " quittance(s) préparée(s), " + result.already + " déjà présentes. Elles restent à régler.",
                  next: { label: "Enregistrer les recettes", href: operationsPath("Transactions") },
                });
                setRevision((value) => value + 1);
              });
            }}>Préparer les loyers de l’exercice</button>
            <PrerequisiteList id={`rents-${p.id}`} causes={rentCauses(p.id, occupants(p.id).length, years)} />
          </article>
        ))}
      </div>}

      {tab === "Banque" && <div id="banque-saisie">
        <SaveNoticeHost place="banque-saisie" notice={notice} onDismiss={dismiss} />
        <p className="form-help">Créez d’abord le compte bancaire, puis importez éventuellement un relevé CSV pour rapprocher.</p>
        <div className="heading-with-help">
          <GlossaryTip id="compte-512" />
          <GlossaryTip id="rapprochement" />
        </div>
        <button id="ajouter-banque" type="button" onClick={() => setEditor({
          title: "Ajouter un compte bancaire", path: "/banks",
          fields: [
            { name: "name", label: "Nom du compte bancaire", group: "Banque" },
            accountField("account_number", "Compte comptable dédié", "512", undefined, "Banque"),
          ],
        })}>Ajouter un compte bancaire</button>
        {banks.map((row) => (
          <article key={row.id} id={`banque-${row.id}`} className="entry-card">
            <h3>{row.name}</h3>
            <p>Compte {row.account_number}</p>
            {row.correction?.locks.map((lock) => <p className="form-help" key={lock.code}>{lock.message}</p>)}
            <div className="entry-actions">
              <button type="button" onClick={() => openBank(row)}>Modifier {row.name}</button>
            </div>
          </article>
        ))}
        {!!banks.length && <>
          <label className="toolbar-field">Banque sélectionnée
            <FitSelect value={bankId} onChange={(e) => {
              setBankId(Number(e.target.value)); setBankOffset(0); setEditor(null); setMatchCandidates(null);
            }}>
              {banks.map((b) => <option key={b.id} value={b.id}>{b.name} · {b.account_number}</option>)}
            </FitSelect>
          </label>
          <CsvImportAssistant
            key={String(bankId)}
            profile="bank"
            summaryTitle="Importer un relevé CSV"
            intro="Téléchargez le modèle (Date, Libellé, Montant, Référence) ou associez les colonnes de votre relevé. L’import seul ne comptabilise rien."
            contentLabel="Contenu CSV"
            textareaId="import-releve"
            anchor="/operations/banque#import-releve"
            causeId="bank-preview-causes"
            postCauseId="bank-post-causes"
            previewLabel="Prévisualiser l’import"
            commitLabel="Confirmer l’import des mouvements"
            busy={busy}
            action={action}
            missingBank={!bankId}
            context={{ bank_account_id: bankId }}
            onImported={() => setRevision((value) => value + 1)}
          />
          <ScreenStatus
            state={bankView}
            onRetry={() => setRevision((value) => value + 1)}
            loading={<p>Chargement du relevé…</p>}
            empty={<p>Aucun mouvement sur ce compte.</p>}
          />
          {entryCauses.length > 0 && <PrerequisiteList id={entryCauseId} causes={entryCauses} />}
          {showsData(bankView) && transactions.map((t) => (
            <article key={t.id} id={`mouvement-${t.id}`} className="entry-card">
              <h3>{t.label} · {formatEuros(t.amount)}</h3>
              <p>{formatIsoDate(t.date)} · {t.external_reference} · {t.matched_entry_id ? "Rapproché avec l’écriture #" + t.matched_entry_id : "À rapprocher"}</p>
              {!t.matched_entry_id ? <>
                <button type="button" disabled={busy} onClick={() => { void action(() => findCandidates(t)); }}>Rapprocher une écriture existante</button>
                <button type="button" disabled={entryCauses.length > 0} aria-describedby={describedBy(entryCauseId, entryCauses)} onClick={() => newOperation(t.amount.startsWith("-") ? "EXPENSE" : "REVENUE", t)}>Créer une opération liée</button>
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
          {matchCandidates && <FrenchForm className="entry-editor" onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            void action(async () => {
              const movement = matchCandidates.transaction;
              await api("/bank/transactions/" + movement.id + "/match", "POST", { entry_line_id: Number(data.get("line")) });
              setMatchCandidates(null); setRevision((v) => v + 1);
              show({
                kind: GLOSSARY.rapprochement.label,
                name: movement.label,
                action: "enregistré",
                targetId: "banque-saisie",
                highlightId: `mouvement-${movement.id}`,
                detail: "Rapprochement enregistré sans nouvelle écriture.",
                next: { label: "Voir le journal", href: "/comptabilite/journal" },
              });
            });
          }}>
            <h3>Rapprocher : {matchCandidates.transaction.label}</h3>
            <p>Vérifiez la référence et la date : un montant égal ne suffit pas.</p>
            {matchCandidates.lines.length ? <>
              <label>Écriture de même montant
                <FitSelect name="line" required>{matchCandidates.lines.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}</FitSelect>
              </label>
              <button type="submit" disabled={busy}>Confirmer le rapprochement</button>
            </> : <p>Aucune écriture de même montant.</p>}
            <button type="button" onClick={() => setMatchCandidates(null)}>Annuler</button>
          </FrenchForm>}
        </>}
      </div>}

      {tab === "Emprunts" && <div id="emprunts-saisie">
        <SaveNoticeHost place="emprunts-saisie" notice={notice} onDismiss={dismiss} />
        <p className="form-help">Chaque ligne de crédit = un emprunt SoloLMNP avec son propre compte 164. Exemple : 15&nbsp;000 € et 195&nbsp;000 € → deux emprunts. Un compte 164 libre est attribué automatiquement si besoin.</p>
        <div className="heading-with-help">
          <GlossaryTip id="emprunt" />
          <GlossaryTip id="compte-164" />
        </div>
        <button id="ajouter-emprunt" type="button" disabled={loanCauses.length > 0} aria-describedby={describedBy(loanCauseId, loanCauses)} onClick={() => {
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
        <PrerequisiteList id={loanCauseId} causes={loanCauses} />
        <PrerequisiteList id={bankCauseId} causes={bankCauses} intro="Déblocage et échéance indisponibles :" />
        {loans.map((l) => (
          <article className="entry-card" id={`emprunt-${l.id}`} key={l.id}>
            <h3>{l.lender}</h3>
            <p>Capital initial : {formatEuros(l.initial_principal)} · Solde comptable : {formatEuros(l.remaining_principal)} · Mensualité : {formatEuros(l.monthly_payment)} + assurance {formatEuros(l.monthly_insurance)} · Compte {l.principal_account}</p>
            {l.correction?.locks.map((lock) => <p className="form-help" key={lock.code}>{lock.message}</p>)}
            <div className="entry-actions">
              <button type="button" onClick={() => openLoan(l)}>Modifier {l.lender}</button>
            </div>
            <button type="button" disabled={bankCauses.length > 0} aria-describedby={describedBy(bankCauseId, bankCauses)} onClick={() => setEditor({
              title: "Déblocage initial : " + l.lender,
              path: "/loans/" + l.id + "/fund",
              retry: true,
              help: "Le montant doit égaler le capital initial. Un seul déblocage non extourné est autorisé.",
              fields: [
                ...settlementFields,
                { name: "amount", label: "Montant débloqué (€)", money: true, value: l.initial_principal, group: "Montant" },
              ],
            })}>Enregistrer le déblocage</button>
            <button type="button" disabled={bankCauses.length > 0} aria-describedby={describedBy(bankCauseId, bankCauses)} onClick={() => {
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
        {!!loans.length && !!banks.length && !openYears.length && (
          <PrerequisiteList id="loan-import-year" causes={openYearCauses(years)} intro="L’import des échéances est indisponible :" />
        )}
        {!!loans.length && !!banks.length && !!openYears.length && <>
          <label className="toolbar-field">Emprunt
            <FitSelect value={loanImportId} onChange={(e) => setLoanImportId(Number(e.target.value))}>
              {loans.map((loan) => (
                <option key={loan.id} value={loan.id}>
                  {loan.lender} · {formatEuros(loan.initial_principal)} · {loan.principal_account}
                </option>
              ))}
            </FitSelect>
          </label>
          <label className="toolbar-field">Exercice
            <FitSelect value={opYearId} onChange={(e) => setOpYearId(Number(e.target.value))}>
              {openYears.map((year) => (
                <option key={year.id} value={year.id}>{year.year}</option>
              ))}
            </FitSelect>
          </label>
          <label className="toolbar-field">Compte bancaire
            <FitSelect value={bankId} onChange={(e) => { setBankId(Number(e.target.value)); setBankOffset(0); }}>
              {banks.map((bank) => (
                <option key={bank.id} value={bank.id}>{bank.name} · {bank.account_number}</option>
              ))}
            </FitSelect>
          </label>
          <CsvImportAssistant
            key={`${loanImportId}-${opYearId}-${bankId}`}
            profile="loan_payments"
            summaryTitle="Importer les échéances depuis Google Sheets ou un CSV"
            intro="Collez l’en-tête et les lignes d’un seul prêt, ou téléchargez le modèle : Prêt, Rang, Date, Date de débit, Capital, Intérêts, Assurance banque, Assurance externe, Autres frais, Total banque. L’en-tête de feuille « Assurance externe à compléter » est reconnu. L’assurance externe prélevée séparément reste une dépense ASS : ne l’incluez pas dans le total banque. Seules les échéances de l’exercice déjà arrivées à leur date seront comptabilisées."
            contentLabel="Lignes du tableau d’amortissement"
            textareaId="import-echeances"
            anchor="/operations/emprunts#import-echeances"
            causeId="loan-preview-causes"
            postCauseId="loan-post-causes"
            previewLabel="Prévisualiser les échéances"
            commitLabel="Comptabiliser les échéances"
            busy={busy}
            action={action}
            missingYear={!opYearId}
            missingBank={!bankId}
            missingLoan={!loanImportId}
            context={{ bank_account_id: bankId, fiscal_year_id: opYearId, loan_id: loanImportId }}
            loanLabel={loanForImport ? `${loanForImport.lender} · ${formatEuros(loanForImport.initial_principal)} · ${loanForImport.principal_account}` : ""}
            onImported={() => setRevision((value) => value + 1)}
          />
        </>}
      </div>}

      {tab === "Transactions" && <div id="transactions-saisie">
        <SaveNoticeHost place="transactions-saisie" notice={notice} onDismiss={dismiss} />
        <p className="form-help">Enregistrez les loyers et charges. La part déductible ne change pas l’écriture : elle est proposée ensuite dans les réintégrations de la liasse. Ne saisissez pas les intérêts déjà ventilés dans une échéance d’emprunt.</p>
        {!!properties.length && !!openYears.length && <>
          <label className="toolbar-field">Bien
            <FitSelect value={opPropertyId} onChange={(e) => setOpPropertyId(Number(e.target.value))}>
              {properties.map((property) => <option key={property.id} value={property.id}>{property.name}</option>)}
            </FitSelect>
          </label>
          <label className="toolbar-field">Exercice
            <FitSelect value={opYearId} onChange={(e) => setOpYearId(Number(e.target.value))}>
              {openYears.map((year) => (
                <option key={year.id} value={year.id}>{year.year}</option>
              ))}
            </FitSelect>
          </label>
          {!!banks.length && <label className="toolbar-field">Compte des lignes payées
            <FitSelect value={bankId} onChange={(e) => setBankId(Number(e.target.value))}>
              {banks.map((b) => <option key={b.id} value={b.id}>{b.name} ({b.account_number})</option>)}
            </FitSelect>
          </label>}
        </>}
        <CsvImportAssistant
          key={`${opPropertyId}-${opYearId}-${bankId}`}
          profile="operations"
          summaryTitle="Importer depuis Google Sheets ou un CSV"
          intro="Téléchargez le modèle ou collez votre feuille. Colonnes : Nature, Date, Date de la pièce, Type, Tiers, Montant, Libellé, Référence de pièce, Justificatif, et Déjà payée. Nature : Recette ou Dépense. Une ligne déjà payée (oui) est réglée sur le compte choisi, sinon elle reste à régler. Le traitement fiscal reste à vérifier."
          contentLabel="Lignes collées ou contenu CSV"
          textareaId="import-operations"
          anchor="/operations/transactions#import-operations"
          causeId="operation-preview-causes"
          postCauseId="operation-post-causes"
          previewLabel="Prévisualiser les justificatifs"
          commitLabel="Comptabiliser les justificatifs"
          busy={busy}
          action={action}
          missingProperty={!opPropertyId}
          missingYear={!opYearId}
          context={{ property_id: opPropertyId, fiscal_year_id: opYearId, bank_account_id: bankId || null }}
          onImported={() => setRevision((value) => value + 1)}
        />
        <div className="form-actions">
          <button type="button" disabled={entryCauses.length > 0} aria-describedby={describedBy(entryCauseId, entryCauses)} onClick={() => newOperation("REVENUE")}>Nouvelle recette</button>
          <button type="button" disabled={entryCauses.length > 0} aria-describedby={describedBy(entryCauseId, entryCauses)} onClick={() => newOperation("EXPENSE")}>Nouvelle dépense</button>
        </div>
        <PrerequisiteList id={entryCauseId} causes={entryCauses} />
        <PrerequisiteList id={bankCauseId} causes={bankCauses} intro="Le règlement reste indisponible :" />
        {showsLoading(bundleView) && <p>Chargement des opérations…</p>}
        {bundleView.phase === "loaded" && operations.length === 0 && <p>Aucune opération enregistrée.</p>}
        {showsData(bundleView) && operations.map((row) => (
          <article key={row.id} id={`operation-${row.id}`} className="entry-card">
            <h3>{enumLabel("operationKind", row.kind)} · {row.description} · {formatEuros(row.amount)}</h3>
            <p>{formatIsoDate(row.date)} · {row.counterparty} · {enumLabel("operationStatus", row.status)}{row.remaining_to_settle !== null && " · Reste à régler : " + formatEuros(row.remaining_to_settle)}</p>
            {row.kind === "LOAN_PAYMENT" && (
              <p>Capital {formatEuros(row.principal)} · Intérêts {formatEuros(row.interest)} · Assurance {formatEuros(row.insurance)} · Frais {formatEuros(row.other_costs)}</p>
            )}
            <button type="button" disabled={busy} aria-busy={busy || undefined} onClick={() => { void action(async () => setDetails(await request<Entry>("/entries/" + row.accounting_entry_id)), "Chargement de l’écriture…"); }}>Voir l’écriture</button>
            {row.status !== "REVERSED" && row.remaining_to_settle && row.remaining_to_settle !== "0.00" && (
              <button type="button" disabled={bankCauses.length > 0} aria-describedby={describedBy(bankCauseId, bankCauses)} onClick={() => setEditor({
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
      </div>}

      {details && (
        <div>
          <h3>{details.entry_number} · {details.label}</h3>
          <ResponsiveTable
            label="Lignes de l’écriture"
            columns={[
              { key: "account", label: "Compte" },
              { key: "label", label: "Libellé", priority: "secondary" },
              { key: "debit", label: "Débit" },
              { key: "credit", label: "Crédit" },
            ]}
            rows={details.lines.map((line, index) => ({
              key: String(index),
              cells: [line.account_number, line.label, line.debit, line.credit],
            }))}
          />
        </div>
      )}
    </>}
  </section>
  </>;
}
