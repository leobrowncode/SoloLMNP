import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { request, cents, amount, type Setup, type Account, type Journal, type Entry, type EntryInput, type Balance, type LedgerLine } from "../api/ledger";
import { describedBy, listed, reversalCause, selectedYearCauses, unbalancedCause } from "./actionCauses";
import PrerequisiteList from "./PrerequisiteList";
import ScreenStatus from "./ScreenStatus";
import {
  beginLoad, defer, failLoad, finishLoad, idleView, showsData, toApiError, type ScreenView,
} from "./screenState";
import {
  DEFAULT_LEDGER_TAB,
  ledgerPath,
  ledgerTabFromSlug,
  type LedgerTab,
} from "../routing/paths";
import { useUnsavedGuard } from "../routing/useUnsavedGuard";
import { DATE_HINT, enumChoices, enumLabel, formatAmount, formatCents, formatIsoDate } from "../lib/format";
import FrenchForm from "../lib/FrenchForm";
import "./ledger.css";
import { BrowsableList } from "./BrowsableList";
import ChartOfAccounts from "./ChartOfAccounts";
import { EmptyState, NoResults } from "./EmptyState";
import InventoryForm from "./InventoryForm";
import { matchesText } from "./listQuery";
import GlossaryTip from "./GlossaryTip";
import { GLOSSARY } from "./glossary";
import { SaveNoticeHost } from "./LocalFeedback";
import { useSaveNotice, type ShowSaveNotice } from "./localFeedback";
import MutationStatus from "./MutationStatus";
import { useMutation } from "./useMutation";
import FitSelect from "../lib/FitSelect";
import { MobileSection, PageAnchors } from "../lib/PageSection";
import { ResponsiveTable } from "../lib/ResponsiveTable";

const blankLine = () => ({ account_number: "", label: "", debit: "0.00", credit: "0.00" });

function entryHaystack(entry: Entry): string {
  return [
    entry.entry_number,
    entry.label,
    entry.piece_reference,
    entry.journal_code,
    enumLabel("entryStatus", entry.status),
    entry.source_type ? enumLabel("entrySource", entry.source_type) : "",
    ...entry.lines.flatMap((line) => [line.account_number, line.account_label, line.label]),
  ].filter((part) => part).join(" ");
}
export default function LedgerPage() {
  const { hash } = useLocation();
  const { tab: tabSlug } = useParams();
  const navigate = useNavigate();
  const resolvedTab = ledgerTabFromSlug(tabSlug);
  const tab: LedgerTab = resolvedTab ?? DEFAULT_LEDGER_TAB;
  const [setup, setSetup] = useState<Setup | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [journals, setJournals] = useState<Journal[]>([]);
  const [year, setYear] = useState(0);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [balance, setBalance] = useState<Balance | null>(null);
  const [ledger, setLedger] = useState<LedgerLine[]>([]);
  const [account, setAccount] = useState("512000");
  const [filter, setFilter] = useState({ journal_code: "", account_number: "", date_from: "", date_to: "", piece: "", source: "" });
  const [entrySearch, setEntrySearch] = useState("");
  const [draft, setDraft] = useState<EntryInput | null>(null);
  const [editing, setEditing] = useState<Entry | null>(null);
  const [confirmation, setConfirmation] = useState<{ action: "validate" | "delete" | "reverse"; entry: Entry } | null>(null);
  const [audit, setAudit] = useState<{ action: string; timestamp: string; details: unknown }[] | null>(null);
  const [actionError, setActionError] = useState("");
  const [catalog, setCatalog] = useState<ScreenView<{ ready: true }>>(() => beginLoad(idleView(), false));
  const [listView, setListView] = useState<ScreenView<{ queryKey: string }>>(idleView());
  const { notice, show, dismiss } = useSaveNotice();
  const { busy, step, run } = useMutation();
  const [revision, setRevision] = useState(0);
  const queryKey = JSON.stringify([year, tab, filter, offset, account]);
  const financialView = tab === "Balance" || tab === "Grand livre";
  const listVisible = showsData(listView) && listView.data.queryKey === queryKey;
  const visibleEntries = entries.filter((entry) => matchesText(entryHaystack(entry), entrySearch));
  const serverFiltered = Object.values(filter).some((value) => value !== "");
  const selectedYear = setup?.years.find((item) => item.id === year);
  const writable = selectedYear?.status === "OPEN";
  const yearCauses = selectedYearCauses(selectedYear?.status);
  const yearCauseId = "ledger-year-causes";
  useUnsavedGuard(!!draft);

  function openTab(next: LedgerTab) {
    navigate(ledgerPath(next));
    setOffset(0);
    setEntries([]);
    setEntrySearch("");
    if (next === "Inventaire") setDraft(null);
  }

  function resetEntryFilters() {
    setFilter({ journal_code: "", account_number: "", date_from: "", date_to: "", piece: "", source: "" });
    setEntrySearch("");
    setOffset(0);
  }

  useEffect(() => {
    let active = true;
    defer(() => {
      if (!active) return;
      setCatalog((current) => beginLoad(current, current.data !== null));
    });
    void Promise.all([request<Setup>("/setup"), request<Account[]>("/accounts"), request<Journal[]>("/journals")]).then(([s, a, j]) => {
      if (!active) return;
      setSetup(s); setAccounts(a); setJournals(j);
      setYear((current) => current || s.years[0]?.id || 0);
      setCatalog(finishLoad({ ready: true }));
    }).catch((reason: unknown) => {
      if (active) setCatalog((current) => failLoad(current, toApiError(reason), current.data !== null));
    });
    return () => { active = false; };
  }, [revision]);

  useEffect(() => {
    let active = true;
    if (!year) {
      defer(() => {
        if (active) setListView(idleView());
      });
      return () => { active = false; };
    }
    defer(() => {
      if (!active) return;
      setListView((current) => {
        const same = !financialView && current.data?.queryKey === queryKey;
        return beginLoad(same ? current : idleView(), same);
      });
    });
    const params = new URLSearchParams({ fiscal_year_id: String(year), limit: "25", offset: String(offset), status: tab === "Brouillons" ? "DRAFT" : "VALIDATED" });
    if (tab === "Inventaire") params.set("source", "INVENTORY");
    else Object.entries(filter).forEach(([key, value]) => { if (value) params.set(key, value); });
    const serverFiltered = tab !== "Inventaire" && Object.values(filter).some((value) => value !== "");
    const load = async () => {
      if (tab === "Balance") {
        const result = await request<Balance>("/years/" + year + "/balance");
        if (!active) return;
        setBalance(result);
        setListView(finishLoad({ queryKey }, () => result.balance.length === 0));
      } else if (tab === "Grand livre") {
        const result = await request<{ lines: LedgerLine[] }>("/years/" + year + "/general-ledger?account_number=" + account);
        if (!active) return;
        setLedger(result.lines);
        setListView(finishLoad({ queryKey }, () => result.lines.length === 0));
      } else {
        const result = await request<{ entries: Entry[]; count: number }>("/entries?" + params);
        if (!active) return;
        setEntries(result.entries);
        setCount(result.count);
        const listed = tab === "Journal" || tab === "Brouillons" || tab === "Inventaire";
        setListView(finishLoad({ queryKey }, () => listed && result.count === 0 && !serverFiltered));
      }
    };
    void load().catch((reason: unknown) => {
      if (!active) return;
      setListView((current) => failLoad(
        current,
        toApiError(reason),
        !financialView && current.data?.queryKey === queryKey,
      ));
    });
    return () => { active = false; };
  }, [year, tab, filter, offset, account, revision, queryKey, financialView]);

  async function mutate(action: () => Promise<unknown>, saved: ShowSaveNotice) {
    await run(async (report) => {
      report("Enregistrement comptable…");
      setActionError("");
      dismiss();
      try {
        await action();
        show(saved);
        setRevision((v) => v + 1);
      } catch (e) {
        setActionError(e instanceof Error ? e.message : "Service indisponible.");
      }
    });
  }
  function formData(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); return new FormData(event.currentTarget);
  }
  function startDraft(entry?: Entry) {
    setEditing(entry || null);
    setDraft(entry ? {
      fiscal_year_id: entry.fiscal_year_id, journal_code: entry.journal_code,
      accounting_date: entry.accounting_date, piece_date: entry.piece_date,
      piece_reference: entry.piece_reference, label: entry.label,
      lines: entry.lines.map(({ account_number, label, debit, credit }) => ({ account_number, label, debit, credit })),
    } : {
      fiscal_year_id: year, journal_code: "OD", accounting_date: selectedYear?.start_date || "",
      piece_date: selectedYear?.start_date || "", piece_reference: "", label: "",
      lines: [blankLine(), blankLine()],
    });
  }
  let totals = "";
  if (draft) {
    try {
      const debit = draft.lines.reduce((sum, line) => sum + cents(line.debit), 0n);
      const credit = draft.lines.reduce((sum, line) => sum + cents(line.credit), 0n);
      totals = "Débit : " + formatCents(debit) + " · Crédit : " + formatCents(credit) + " · Écart : " + formatCents(debit - credit);
    } catch { totals = "Saisissez des montants positifs avec deux décimales au maximum."; }
  }

  return <>
    {tabSlug && !resolvedTab && <Navigate to={ledgerPath(DEFAULT_LEDGER_TAB)} replace />}
    <section id="comptabilite" className="ledger-page" aria-labelledby="ledger-title" data-screen-phase={catalog.phase}>
    <div className="heading-with-help">
      <h2 id="ledger-title">Votre comptabilité</h2>
      <GlossaryTip id="journal" />
      <GlossaryTip id="brouillon" />
      <GlossaryTip id="extourne" />
      <GlossaryTip id="balance" />
      <GlossaryTip id="grand-livre" />
    </div>
    <p>Seules les écritures validées alimentent le journal, le grand livre et la balance. Leur validation est définitive.</p>
    <PageAnchors
      label="Sections de la comptabilité"
      links={[
        { href: "#reglages-comptables", label: "Réglages" },
        { href: "#exercice", label: "Exercice" },
        { href: "#ecriture-saisie", label: "Écritures" },
      ]}
    />
    <MutationStatus step={step} />
    {actionError && <p role="alert" className="ledger-error">{actionError}</p>}
    <ScreenStatus
      state={catalog}
      onRetry={() => setRevision((value) => value + 1)}
      loading={<p>Chargement de la comptabilité…</p>}
    />
    <MobileSection
      id="reglages-comptables"
      title="Réglages comptables"
      open={!setup?.activity || (setup?.years.length ?? 0) === 0 || hash === "#ajouter-exercice" || hash === "#identite-liasse" || hash === "#reglages-comptables"}
    >
    <SaveNoticeHost place="reglages-comptables" notice={notice} onDismiss={dismiss} />
    {setup && !setup.activity && <FrenchForm id="creer-activite" tabIndex={-1} onSubmit={(e) => {
      const data = formData(e);
      const name = String(data.get("name") ?? "");
      void mutate(() => request("/activity", "POST", { activity_name: name, activity_start_date: data.get("start") }), {
        kind: "Activité",
        name: name || "nouvelle activité",
        action: "créée",
        targetId: "reglages-comptables",
        detail: "Activité créée.",
        next: { label: "Renseigner le SIREN", href: "#identite-liasse" },
      });
    }}>
      <h3>Initialiser votre activité</h3>
      <p>Pour une activité déjà existante, les soldes antérieurs devront être repris par des écritures d’à-nouveaux justifiées. La création de cet espace ne reconstitue pas votre historique.</p>
      <GlossaryTip id="a-nouveaux" />
      <label>Nom de l’activité<input name="name" required maxLength={200} /></label>
      <label>Date réelle de début<input name="start" type="date" lang="fr" required /><span className="field-hint">{DATE_HINT}</span></label>
      <button disabled={busy}>Créer l’activité</button>
    </FrenchForm>}
    {setup?.activity && <FrenchForm onSubmit={(e) => {
      const data = formData(e);
      const siren = String(data.get("siren") ?? "");
      void mutate(() => request("/activity/identity", "POST", {
        siren,
        siret: String(data.get("siret") ?? ""),
      }), {
        kind: GLOSSARY.siren.label,
        name: siren || "liasse",
        action: "enregistré",
        targetId: "reglages-comptables",
        detail: "Identité enregistrée. Elle apparaîtra en tête de la liasse.",
        next: { label: "Ajouter un exercice", href: "#ajouter-exercice" },
      });
    }}>
      <div className="heading-with-help">
        <h3 id="identite-liasse" tabIndex={-1}>Identité pour la liasse</h3>
        <GlossaryTip id="liasse" />
        <GlossaryTip id="siren" />
      </div>
      <p>Le SIRET figure sur la 2031. Laissez vide si vous ne l’avez pas encore.</p>
      <label>SIREN<input name="siren" inputMode="numeric" maxLength={9} defaultValue={setup.activity.siren ?? ""} /></label>
      <label>SIRET<input name="siret" inputMode="numeric" maxLength={14} defaultValue={setup.activity.siret ?? ""} /></label>
      <button disabled={busy}>Enregistrer l’identité</button>
    </FrenchForm>}
    {setup?.activity && <details id="ajouter-exercice" tabIndex={-1} open={!setup.years.length || hash === "#ajouter-exercice"}>
      <summary>{setup.activity.activity_name} · Ajouter un exercice</summary>
      <FrenchForm onSubmit={(e) => {
        const data = formData(e);
        const end = String(data.get("end") ?? "");
        const vintage = String(data.get("vintage") ?? "");
        void mutate(() => request("/years", "POST", {
          year: Number(end.slice(0, 4)), start_date: data.get("start"),
          end_date: end, fiscal_vintage: vintage,
        }), {
          kind: GLOSSARY.exercice.label,
          name: vintage || end.slice(0, 4) || "nouvel exercice",
          action: "créé",
          targetId: "reglages-comptables",
          detail: "Exercice créé.",
          next: { label: "Saisir une écriture", href: `${ledgerPath("Brouillons")}#nouvelle-ecriture` },
        });
      }}>
        <label>Début de l’exercice<input name="start" type="date" lang="fr" required /><span className="field-hint">{DATE_HINT}</span></label>
        <label>Fin de l’exercice<input name="end" type="date" lang="fr" required /><span className="field-hint">{DATE_HINT}</span></label>
        <label>Millésime fiscal<input name="vintage" pattern="[0-9]{4}" required placeholder="2026" /></label>
        <GlossaryTip id="millesime" />
        <GlossaryTip id="exercice" />
        <button disabled={busy}>Créer l’exercice</button>
      </FrenchForm>
    </details>}
    </MobileSection>
    {!!setup?.years.length && <>
      <PrerequisiteList id={yearCauseId} causes={yearCauses} intro="Saisie indisponible :" />
      <label id="exercice" tabIndex={-1}>Exercice<FitSelect value={year} onChange={(e) => { setYear(Number(e.target.value)); setDraft(null); setConfirmation(null); setOffset(0); setBalance(null); setLedger([]); setEntries([]); }}>
        {setup.years.map((y) => <option key={y.id} value={y.id}>{y.year} · {enumLabel("yearStatus", y.status)}</option>)}
      </FitSelect></label>
      <nav aria-label="Vues comptables" className="ledger-tabs">{(["Brouillons", "Journal", "Grand livre", "Balance", "Plan comptable", "Inventaire"] as LedgerTab[]).map((name) =>
        <button key={name} aria-pressed={tab === name} onClick={() => openTab(name)}>{name}</button>)}</nav>
      <div id="ecriture-saisie">
      <SaveNoticeHost place="ecriture-saisie" notice={notice} onDismiss={dismiss} />
      {tab === "Brouillons" && <button id="nouvelle-ecriture" disabled={!writable || busy} aria-describedby={describedBy(yearCauseId, yearCauses)} onClick={() => startDraft()}>Nouvelle écriture</button>}
      {tab === "Inventaire" && selectedYear && <div id="inventaire-saisie"><InventoryForm key={year} year={selectedYear} accounts={accounts} journals={journals} onPosted={() => setRevision((v) => v + 1)} /></div>}
      {tab === "Inventaire" && <>
        <p className="list-group-title">Écritures d’inventaire de l’exercice</p>
        <ScreenStatus
          state={listView}
          onRetry={() => setRevision((value) => value + 1)}
          loading={<p>Chargement…</p>}
          empty={<EmptyState title="Aucune écriture d’inventaire pour cet exercice." reason="Un inventaire validé apparaît ici. Préparez-le dans le formulaire : la confirmation crée l’écriture définitive." action={{ label: "Préparer un inventaire", href: "#inventaire-saisie" }} />}
        />
        {listVisible && entries.length > 0 && (
          <BrowsableList
            items={entries}
            searchLabel="Rechercher une écriture d’inventaire"
            text={entryHaystack}
            statusOf={(entry) => entry.status}
            statusChoices={enumChoices("entryStatus")}
            emptyTitle="Aucune écriture d’inventaire pour cet exercice."
            emptyReason="Un inventaire validé apparaît ici."
            noResultsReason="Aucune écriture d’inventaire ne correspond à la recherche ou au statut."
          >
            {(rows) => rows.map((entry) => (
              <article className="entry-card" key={entry.id}>
                <h3>{entry.entry_number || "Inventaire #" + entry.id} · {entry.label}</h3>
                <p>{formatIsoDate(entry.accounting_date)} · {entry.journal_code} · Pièce {entry.piece_reference} · {enumLabel("entryStatus", entry.status)}</p>
              </article>
            ))}
          </BrowsableList>
        )}
      </>}
      {draft && <FrenchForm className="entry-editor" onSubmit={(e) => {
        e.preventDefault();
        const savedLabel = draft.label || "brouillon";
        const wasEditing = Boolean(editing);
        void mutate(async () => {
          const body = { ...draft, lines: draft.lines.map((line) => ({ ...line, debit: amount(cents(line.debit)), credit: amount(cents(line.credit)) })) };
          await request(editing ? "/entries/" + editing.id : "/entries", editing ? "PUT" : "POST",
            editing ? { ...body, expected_version: editing.version } : body);
          setDraft(null); setEditing(null);
        }, {
          kind: GLOSSARY.ecriture.label,
          name: savedLabel,
          action: wasEditing ? "modifiée" : "enregistrée",
          targetId: "ecriture-saisie",
          detail: "Brouillon enregistré. Vérifiez-le avant validation.",
          next: { label: "Valider dans les brouillons", href: `${ledgerPath("Brouillons")}#ecriture-saisie` },
        });
      }}>
        <h3>{editing ? "Modifier le brouillon" : "Nouvelle écriture"}</h3>
        <label>Journal<FitSelect value={draft.journal_code} onChange={(e) => setDraft({ ...draft, journal_code: e.target.value })}>{journals.filter((j) => j.active).map((j) => <option key={j.code} value={j.code}>{j.code} · {j.label}</option>)}</FitSelect></label>
        <label>Date comptable<input type="date" lang="fr" required min={selectedYear?.start_date} max={selectedYear?.end_date} value={draft.accounting_date} onChange={(e) => setDraft({ ...draft, accounting_date: e.target.value })} /><span className="field-hint">{DATE_HINT}</span></label>
        <label>Date de la pièce<input type="date" lang="fr" required value={draft.piece_date} onChange={(e) => setDraft({ ...draft, piece_date: e.target.value })} /><span className="field-hint">{DATE_HINT}</span></label>
        <label>Référence de la pièce<input required value={draft.piece_reference} onChange={(e) => setDraft({ ...draft, piece_reference: e.target.value })} /></label>
        <label>Libellé de l’écriture<input required value={draft.label} onChange={(e) => setDraft({ ...draft, label: e.target.value })} /></label>
        {draft.lines.map((line, index) => <fieldset key={index}>
          <legend>Ligne {index + 1}</legend>
          <label>Compte<FitSelect required value={line.account_number} onChange={(e) => setDraft({ ...draft, lines: draft.lines.map((l, i) => i === index ? { ...l, account_number: e.target.value } : l) })}>
            <option value="">Choisir un compte</option>{accounts.filter((a) => a.active).map((a) => <option key={a.number} value={a.number}>{a.number} · {a.label}</option>)}
          </FitSelect></label>
          {(["label", "debit", "credit"] as const).map((key) => <label key={key}>{key === "label" ? "Libellé" : key === "debit" ? "Débit (€)" : "Crédit (€)"}<input required inputMode={key === "label" ? "text" : "decimal"} lang={key === "label" ? undefined : "fr"} placeholder={key === "label" ? undefined : "1 234,56"} data-money={key === "label" ? undefined : "true"} value={line[key]} onChange={(e) => setDraft({ ...draft, lines: draft.lines.map((l, i) => i === index ? { ...l, [key]: e.target.value } : l) })} /></label>)}
          <button type="button" disabled={draft.lines.length <= 2} onClick={() => setDraft({ ...draft, lines: draft.lines.filter((_, i) => i !== index) })}>Retirer la ligne {index + 1}</button>
        </fieldset>)}
        <p aria-live="polite">{totals}</p>
        <button type="button" disabled={draft.lines.length >= 100} onClick={() => setDraft({ ...draft, lines: [...draft.lines, blankLine()] })}>Ajouter une ligne</button>
        <button disabled={busy}>Enregistrer le brouillon</button>
        <button type="button" onClick={() => setDraft(null)}>Annuler la saisie</button>
      </FrenchForm>}
      {(tab === "Journal" || tab === "Brouillons") && <>
        <label className="toolbar-field">Rechercher une écriture
          <input type="search" value={entrySearch} autoComplete="off" onChange={(event) => setEntrySearch(event.target.value)} />
        </label>
        <details><summary>Filtres</summary><div className="ledger-filters">
          {Object.entries(filter).filter(([key]) => key !== "source").map(([key, value]) => <label key={key}>{{ journal_code: "Code journal", account_number: "Numéro de compte", date_from: "Du", date_to: "Au", piece: "Pièce" }[key]}<input type={key.startsWith("date") ? "date" : "text"} lang={key.startsWith("date") ? "fr" : undefined} value={value} onChange={(e) => { setFilter({ ...filter, [key]: e.target.value }); setOffset(0); }} />{key.startsWith("date") ? <span className="field-hint">{DATE_HINT}</span> : null}</label>)}
          <label>Source<FitSelect value={filter.source} onChange={(e) => { setFilter({ ...filter, source: e.target.value }); setOffset(0); }}>
            <option value="">Toutes les sources</option>
            {enumChoices("entrySource").map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </FitSelect></label>
        </div></details>
        <ScreenStatus
          state={listView}
          onRetry={() => setRevision((value) => value + 1)}
          loading={<p>Chargement…</p>}
          empty={
            <EmptyState
              title="Aucune écriture pour cette vue."
              reason={tab === "Journal"
                ? "Validées uniquement. Un brouillon reste hors des états comptables tant qu’il n’est pas validé."
                : "Hors états comptables. Validez un brouillon pour qu’il entre dans le journal."}
              action={tab === "Journal"
                ? { label: "Ouvrir les brouillons", href: ledgerPath("Brouillons") }
                : { label: "Saisir une écriture", onClick: () => startDraft() }}
            />
          }
        />
        {listVisible && count === 0 && serverFiltered && (
          <NoResults reason="Aucune écriture ne correspond aux filtres." onReset={resetEntryFilters} />
        )}
        {listVisible && entries.length > 0 && visibleEntries.length === 0 && (
          <NoResults reason="Aucune écriture ne correspond à la recherche ou aux filtres." onReset={resetEntryFilters} />
        )}
        {listVisible && visibleEntries.length > 0 && <p>{count} écriture(s) · {tab === "Journal" ? "validées uniquement" : "hors états comptables"}</p>}
        {listVisible && visibleEntries.map((entry) => {
          const balanceId = `entry-${entry.id}-balance`;
          const reversalId = `entry-${entry.id}-reversal`;
          return <article className="entry-card" key={entry.id}>
          <h3>{entry.entry_number || "Brouillon #" + entry.id} · {entry.label}</h3>
          <p>{formatIsoDate(entry.accounting_date)} · {entry.journal_code} · Pièce {entry.piece_reference} · {enumLabel("entryStatus", entry.status)}</p>
          <ResponsiveTable
            label="Lignes de l’écriture"
            columns={[
              { key: "account", label: "Compte" },
              { key: "label", label: "Libellé", priority: "secondary" },
              { key: "debit", label: "Débit €" },
              { key: "credit", label: "Crédit €" },
            ]}
            rows={entry.lines.map((line, index) => ({
              key: String(index),
              cells: [line.account_number, line.label, formatAmount(line.debit), formatAmount(line.credit)],
            }))}
            footerRow={<tr><th colSpan={2}>{entry.balanced ? "Équilibrée" : "Déséquilibrée"}</th><td>{formatAmount(entry.total_debit)}</td><td>{formatAmount(entry.total_credit)}</td></tr>}
            footerNote={`${entry.balanced ? "Équilibrée" : "Déséquilibrée"} · Débit ${formatAmount(entry.total_debit)} · Crédit ${formatAmount(entry.total_credit)}`}
          />
          {entry.status === "DRAFT" ? <>
            <button id={`ecriture-${entry.id}`} disabled={!writable || busy} aria-describedby={describedBy(yearCauseId, yearCauses)} onClick={() => startDraft(entry)}>Modifier</button>
            <button disabled={!writable || busy || !entry.balanced} aria-describedby={describedBy(yearCauseId, yearCauses, !entry.balanced ? balanceId : undefined)} onClick={() => setConfirmation({ action: "validate", entry })}>Valider</button>
            {!entry.balanced && <PrerequisiteList id={balanceId} causes={listed(unbalancedCause(entry.id))} />}
            <button disabled={!writable || busy} aria-describedby={describedBy(yearCauseId, yearCauses)} onClick={() => setConfirmation({ action: "delete", entry })}>Supprimer</button>
          </> : <>
            <button disabled={!writable || busy || !!entry.reversal_of_id} aria-describedby={describedBy(yearCauseId, yearCauses, entry.reversal_of_id ? reversalId : undefined)} onClick={() => setConfirmation({ action: "reverse", entry })}>Extourner</button>
            {!!entry.reversal_of_id && <PrerequisiteList id={reversalId} causes={listed(reversalCause())} />}
          </>}
          <button onClick={() => { void request<{ action: string; timestamp: string; details: unknown }[]>("/entries/" + entry.id + "/events").then(setAudit).catch((reason: unknown) => setActionError(toApiError(reason).message)); }}>Voir l’historique</button>
        </article>;
        })}
        <button disabled={!offset} onClick={() => setOffset(offset - 25)}>Page précédente</button>
        <button disabled={offset + 25 >= count} onClick={() => setOffset(offset + 25)}>Page suivante</button>
      </>}
      </div>
      {confirmation && <FrenchForm className="entry-editor" onSubmit={(e) => {
        const data = formData(e); const { action, entry } = confirmation;
        const savedLabel = entry.label;
        const savedAction = action;
        void mutate(async () => {
          await request("/entries/" + entry.id + (savedAction === "delete" ? "" : "/" + savedAction), savedAction === "delete" ? "DELETE" : "POST",
            savedAction === "reverse" ? { accounting_date: data.get("date"), piece_reference: data.get("piece"), reason: data.get("reason") } : { expected_version: entry.version });
          setConfirmation(null);
        }, {
          kind: GLOSSARY.ecriture.label,
          name: savedLabel,
          action: savedAction === "validate" ? "validée" : savedAction === "delete" ? "supprimée" : "extournée",
          targetId: "ecriture-saisie",
          detail: savedAction === "validate"
            ? "Validation enregistrée. Le numéro est définitif."
            : savedAction === "delete"
              ? "Brouillon supprimé. Son historique est conservé."
              : "Extourne enregistrée. L’écriture d’origine est conservée.",
          next: savedAction === "delete"
            ? undefined
            : { label: "Voir le journal", href: ledgerPath("Journal") },
        });
      }}>
        <h3>Confirmer : {confirmation.entry.label}</h3>
        <p>{confirmation.action === "validate" ? "La validation attribue un numéro définitif. Cette écriture ne pourra plus être modifiée ou supprimée." : confirmation.action === "delete" ? "Le brouillon sera supprimé. Son historique sera conservé." : "Une nouvelle écriture inversera les débits et crédits. L’écriture d’origine sera conservée."}</p>
        {confirmation.action === "reverse" && <>
          <label>Date de l’extourne<input name="date" type="date" lang="fr" required min={selectedYear?.start_date} max={selectedYear?.end_date} /><span className="field-hint">{DATE_HINT}</span></label>
          <label>Pièce de l’extourne<input name="piece" required /></label>
          <label>Motif<input name="reason" required minLength={5} maxLength={300} /></label>
        </>}
        <button disabled={busy}>Confirmer {confirmation.action === "validate" ? "la validation" : confirmation.action === "delete" ? "la suppression" : "l’extourne"}</button>
        <button type="button" onClick={() => setConfirmation(null)}>Annuler</button>
      </FrenchForm>}
      {audit && <details open><summary>Historique de l’écriture</summary>{audit.map((item, i) => <div key={i}><strong>{item.action} · {item.timestamp}</strong><pre>{JSON.stringify(item.details, null, 2)}</pre></div>)}<button onClick={() => setAudit(null)}>Fermer l’historique</button></details>}
      {tab === "Balance" && <>
        <ScreenStatus
          state={listView}
          onRetry={() => setRevision((value) => value + 1)}
          loading={<p>Chargement…</p>}
          empty={<EmptyState title="Aucune ligne de balance." reason="La balance reprend les écritures validées. Elle reste vide tant qu’aucune n’est validée sur cet exercice." action={{ label: "Ouvrir les brouillons", href: ledgerPath("Brouillons") }} />}
        />
        {listVisible && balance?.balance && balance.balance.length > 0 && (
          <BrowsableList
            items={balance.balance}
            searchLabel="Rechercher dans la balance"
            text={(row) => `${row.account_number} ${row.label}`}
            emptyTitle="Aucune ligne de balance."
            emptyReason="La balance reprend les écritures validées."
            noResultsReason="Aucun compte de la balance ne correspond à la recherche."
          >
            {(rows) => <ResponsiveTable
          label="Balance générale"
          caption="Balance générale · écritures validées"
          columns={[
            { key: "account", label: "Compte" },
            { key: "label", label: "Libellé" },
            { key: "debit", label: "Total débit", priority: "secondary" },
            { key: "credit", label: "Total crédit", priority: "secondary" },
            { key: "debitBalance", label: "Solde débiteur" },
            { key: "creditBalance", label: "Solde créditeur" },
          ]}
          rows={rows.map((row) => ({
            key: row.account_number,
            cells: [
              row.account_number,
              row.label,
              formatAmount(row.total_debit),
              formatAmount(row.total_credit),
              formatAmount(row.debit_balance),
              formatAmount(row.credit_balance),
            ],
          }))}
          footerRow={<tr><th colSpan={2}>{balance.balanced ? "Balance équilibrée" : "ERREUR : balance déséquilibrée"}</th><td>{formatAmount(balance.total_debit)}</td><td>{formatAmount(balance.total_credit)}</td><td colSpan={2}>EUR</td></tr>}
          footerNote={`${balance.balanced ? "Balance équilibrée" : "ERREUR : balance déséquilibrée"} · Débit ${formatAmount(balance.total_debit)} · Crédit ${formatAmount(balance.total_credit)} · EUR`}
        />}</BrowsableList>
        )}
      </>}
      {tab === "Grand livre" && <>
        <label>Compte du grand livre<FitSelect value={account} onChange={(e) => { setAccount(e.target.value); setLedger([]); }}>{accounts.map((a) => <option key={a.number} value={a.number}>{a.number} · {a.label}</option>)}</FitSelect></label>
        <ScreenStatus
          state={listView}
          onRetry={() => setRevision((value) => value + 1)}
          loading={<p>Chargement…</p>}
          empty={<EmptyState title="Aucune ligne dans ce grand livre." reason="Aucune écriture validée n’a mouvementé ce compte." action={{ label: "Saisir une écriture", href: ledgerPath("Brouillons") }} />}
        />
        {listVisible && ledger.length > 0 && (
          <BrowsableList
            items={ledger}
            searchLabel="Rechercher dans le grand livre"
            text={(line) => `${line.entry_number} ${line.label} ${line.date}`}
            emptyTitle="Aucune ligne dans ce grand livre."
            emptyReason="Aucune écriture validée n’a mouvementé ce compte."
            noResultsReason="Aucune ligne du grand livre ne correspond à la recherche."
          >
            {(rows) => <ResponsiveTable
          label="Grand livre"
          caption="Solde positif : débiteur · négatif : créditeur"
          columns={[
            { key: "date", label: "Date" },
            { key: "entry", label: "Écriture", priority: "secondary" },
            { key: "label", label: "Libellé" },
            { key: "debit", label: "Débit" },
            { key: "credit", label: "Crédit" },
            { key: "balance", label: "Solde" },
          ]}
          rows={rows.map((line, index) => ({
            key: `${line.entry_number}-${index}`,
            cells: [formatIsoDate(line.date), line.entry_number, line.label, formatAmount(line.debit), formatAmount(line.credit), formatAmount(line.balance)],
          }))}
        />}</BrowsableList>
        )}
      </>}
      {tab === "Plan comptable" && <>
        <p>Le plan initial est configurable. Les libellés des comptes utilisés par des écritures validées sont figés.</p>
        <ChartOfAccounts
          accounts={accounts}
          busy={busy}
          notice={notice}
          onDismiss={dismiss}
          onCreate={(account) => {
            void mutate(() => request("/accounts", "POST", account), {
              kind: "Compte",
              name: `${account.number} ${account.label}`,
              action: "créé",
              targetId: "ajouter-compte",
              highlightId: `compte-${account.number}`,
              next: { label: "Saisir une écriture", href: `${ledgerPath("Brouillons")}#nouvelle-ecriture` },
            });
          }}
          onToggle={(account) => {
            const active = !account.active;
            void mutate(
              () => request("/accounts/" + account.number + "/active", "PATCH", { active }),
              {
                kind: "Compte",
                name: `${account.number} ${account.label}`,
                action: active ? "réactivé" : "désactivé",
                targetId: `compte-${account.number}`,
                next: active
                  ? { label: "Saisir une écriture", href: `${ledgerPath("Brouillons")}#nouvelle-ecriture` }
                  : undefined,
              },
            );
          }}
        />
      </>}
    </>}
  </section>
  </>;
}
