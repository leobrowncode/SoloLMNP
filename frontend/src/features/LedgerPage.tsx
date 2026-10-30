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
import "./ledger.css";
import InventoryForm from "./InventoryForm";
import GlossaryTip from "./GlossaryTip";
import MutationStatus from "./MutationStatus";
import { useMutation } from "./useMutation";

const blankLine = () => ({ account_number: "", label: "", debit: "0.00", credit: "0.00" });
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
  const [draft, setDraft] = useState<EntryInput | null>(null);
  const [editing, setEditing] = useState<Entry | null>(null);
  const [confirmation, setConfirmation] = useState<{ action: "validate" | "delete" | "reverse"; entry: Entry } | null>(null);
  const [audit, setAudit] = useState<{ action: string; timestamp: string; details: unknown }[] | null>(null);
  const [actionError, setActionError] = useState("");
  const [catalog, setCatalog] = useState<ScreenView<{ ready: true }>>(() => beginLoad(idleView(), false));
  const [listView, setListView] = useState<ScreenView<{ queryKey: string }>>(idleView());
  const [message, setMessage] = useState("");
  const { busy, step, run } = useMutation();
  const [revision, setRevision] = useState(0);
  const queryKey = JSON.stringify([year, tab, filter, offset, account]);
  const financialView = tab === "Balance" || tab === "Grand livre";
  const listVisible = showsData(listView) && listView.data.queryKey === queryKey;
  const selectedYear = setup?.years.find((item) => item.id === year);
  const writable = selectedYear?.status === "OPEN";
  const yearCauses = selectedYearCauses(selectedYear?.status);
  const yearCauseId = "ledger-year-causes";
  useUnsavedGuard(!!draft);

  function openTab(next: LedgerTab) {
    navigate(ledgerPath(next));
    setOffset(0);
    setEntries([]);
    if (next === "Inventaire") setDraft(null);
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
    Object.entries(filter).forEach(([key, value]) => { if (value) params.set(key, value); });
    const load = async () => {
      if (tab === "Balance") {
        const result = await request<Balance>("/years/" + year + "/balance");
        if (!active) return;
        setBalance(result);
        setListView(finishLoad({ queryKey }));
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
        const listed = tab === "Journal" || tab === "Brouillons";
        setListView(finishLoad({ queryKey }, () => listed && result.count === 0));
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

  async function mutate(action: () => Promise<unknown>, success: string) {
    await run(async (report) => {
      report("Enregistrement comptable…");
      setActionError(""); setMessage("");
      try { await action(); setMessage(success); setRevision((v) => v + 1); }
      catch (e) { setActionError(e instanceof Error ? e.message : "Service indisponible."); }
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
      totals = "Débit : " + amount(debit) + " € · Crédit : " + amount(credit) + " € · Écart : " + amount(debit - credit) + " €";
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
    <MutationStatus step={step} />
    {actionError && <p role="alert" className="ledger-error">{actionError}</p>}
    {message && <p role="status">{message}</p>}
    <ScreenStatus
      state={catalog}
      onRetry={() => setRevision((value) => value + 1)}
      loading={<p>Chargement de la comptabilité…</p>}
    />
    {setup && !setup.activity && <form id="creer-activite" tabIndex={-1} onSubmit={(e) => {
      const data = formData(e);
      void mutate(() => request("/activity", "POST", { activity_name: data.get("name"), activity_start_date: data.get("start") }), "Activité créée.");
    }}>
      <h3>Initialiser votre activité</h3>
      <p>Pour une activité déjà existante, les soldes antérieurs devront être repris par des écritures d’à-nouveaux justifiées. La création de cet espace ne reconstitue pas votre historique.</p>
      <GlossaryTip id="a-nouveaux" />
      <label>Nom de l’activité<input name="name" required maxLength={200} /></label>
      <label>Date réelle de début<input name="start" type="date" required /></label>
      <button disabled={busy}>Créer l’activité</button>
    </form>}
    {setup?.activity && <form onSubmit={(e) => {
      const data = formData(e);
      void mutate(() => request("/activity/identity", "POST", {
        siren: String(data.get("siren") ?? ""),
        siret: String(data.get("siret") ?? ""),
      }), "Identité enregistrée. Elle apparaîtra en tête de la liasse.");
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
    </form>}
    {setup?.activity && <details id="ajouter-exercice" tabIndex={-1} open={!setup.years.length || hash === "#ajouter-exercice"}>
      <summary>{setup.activity.activity_name} · Ajouter un exercice</summary>
      <form onSubmit={(e) => {
        const data = formData(e);
        void mutate(() => request("/years", "POST", {
          year: Number(String(data.get("end")).slice(0, 4)), start_date: data.get("start"),
          end_date: data.get("end"), fiscal_vintage: data.get("vintage"),
        }), "Exercice créé.");
      }}>
        <label>Début de l’exercice<input name="start" type="date" required /></label>
        <label>Fin de l’exercice<input name="end" type="date" required /></label>
        <label>Millésime fiscal<input name="vintage" pattern="[0-9]{4}" required placeholder="2026" /></label>
        <GlossaryTip id="millesime" />
        <GlossaryTip id="exercice" />
        <button disabled={busy}>Créer l’exercice</button>
      </form>
    </details>}
    {!!setup?.years.length && <>
      <PrerequisiteList id={yearCauseId} causes={yearCauses} intro="Saisie indisponible :" />
      <label id="exercice" tabIndex={-1}>Exercice<select value={year} onChange={(e) => { setYear(Number(e.target.value)); setDraft(null); setConfirmation(null); setOffset(0); setBalance(null); setLedger([]); setEntries([]); }}>
        {setup.years.map((y) => <option key={y.id} value={y.id}>{y.year} · {y.status === "OPEN" ? "ouvert" : y.status === "CLOSED" ? "clôturé" : "prêt à clôturer"}</option>)}
      </select></label>
      <nav aria-label="Vues comptables" className="ledger-tabs">{(["Brouillons", "Journal", "Grand livre", "Balance", "Plan comptable", "Inventaire"] as LedgerTab[]).map((name) =>
        <button key={name} aria-pressed={tab === name} onClick={() => openTab(name)}>{name}</button>)}</nav>
      {tab === "Brouillons" && <button id="nouvelle-ecriture" disabled={!writable || busy} aria-describedby={describedBy(yearCauseId, yearCauses)} onClick={() => startDraft()}>Nouvelle écriture</button>}
      {tab === "Inventaire" && selectedYear && <InventoryForm key={year} year={selectedYear} accounts={accounts} journals={journals} onPosted={() => setRevision((v) => v + 1)} />}
      {draft && <form className="entry-editor" onSubmit={(e) => {
        e.preventDefault();
        void mutate(async () => {
          const body = { ...draft, lines: draft.lines.map((line) => ({ ...line, debit: amount(cents(line.debit)), credit: amount(cents(line.credit)) })) };
          await request(editing ? "/entries/" + editing.id : "/entries", editing ? "PUT" : "POST",
            editing ? { ...body, expected_version: editing.version } : body);
          setDraft(null); setEditing(null);
        }, "Brouillon enregistré. Vérifiez-le avant validation.");
      }}>
        <h3>{editing ? "Modifier le brouillon" : "Nouvelle écriture"}</h3>
        <label>Journal<select value={draft.journal_code} onChange={(e) => setDraft({ ...draft, journal_code: e.target.value })}>{journals.filter((j) => j.active).map((j) => <option key={j.code} value={j.code}>{j.code} · {j.label}</option>)}</select></label>
        <label>Date comptable<input type="date" required min={selectedYear?.start_date} max={selectedYear?.end_date} value={draft.accounting_date} onChange={(e) => setDraft({ ...draft, accounting_date: e.target.value })} /></label>
        <label>Date de la pièce<input type="date" required value={draft.piece_date} onChange={(e) => setDraft({ ...draft, piece_date: e.target.value })} /></label>
        <label>Référence de la pièce<input required value={draft.piece_reference} onChange={(e) => setDraft({ ...draft, piece_reference: e.target.value })} /></label>
        <label>Libellé de l’écriture<input required value={draft.label} onChange={(e) => setDraft({ ...draft, label: e.target.value })} /></label>
        {draft.lines.map((line, index) => <fieldset key={index}>
          <legend>Ligne {index + 1}</legend>
          <label>Compte<select required value={line.account_number} onChange={(e) => setDraft({ ...draft, lines: draft.lines.map((l, i) => i === index ? { ...l, account_number: e.target.value } : l) })}>
            <option value="">Choisir un compte</option>{accounts.filter((a) => a.active).map((a) => <option key={a.number} value={a.number}>{a.number} · {a.label}</option>)}
          </select></label>
          {(["label", "debit", "credit"] as const).map((key) => <label key={key}>{key === "label" ? "Libellé" : key === "debit" ? "Débit (€)" : "Crédit (€)"}<input required inputMode={key === "label" ? "text" : "decimal"} value={line[key]} onChange={(e) => setDraft({ ...draft, lines: draft.lines.map((l, i) => i === index ? { ...l, [key]: e.target.value } : l) })} /></label>)}
          <button type="button" disabled={draft.lines.length <= 2} onClick={() => setDraft({ ...draft, lines: draft.lines.filter((_, i) => i !== index) })}>Retirer la ligne {index + 1}</button>
        </fieldset>)}
        <p aria-live="polite">{totals}</p>
        <button type="button" disabled={draft.lines.length >= 100} onClick={() => setDraft({ ...draft, lines: [...draft.lines, blankLine()] })}>Ajouter une ligne</button>
        <button disabled={busy}>Enregistrer le brouillon</button>
        <button type="button" onClick={() => setDraft(null)}>Annuler la saisie</button>
      </form>}
      {(tab === "Journal" || tab === "Brouillons") && <>
        <details><summary>Filtres</summary><div className="ledger-filters">
          {Object.entries(filter).filter(([key]) => key !== "source").map(([key, value]) => <label key={key}>{{ journal_code: "Code journal", account_number: "Numéro de compte", date_from: "Du", date_to: "Au", piece: "Pièce" }[key]}<input type={key.startsWith("date") ? "date" : "text"} value={value} onChange={(e) => { setFilter({ ...filter, [key]: e.target.value }); setOffset(0); }} /></label>)}
          <label>Source<select value={filter.source} onChange={(e) => { setFilter({ ...filter, source: e.target.value }); setOffset(0); }}>
            <option value="">Toutes les sources</option>
            {Object.entries({ MANUAL: "Saisie manuelle", REVERSAL: "Extournes", REVENUE: "Recettes", EXPENSE: "Dépenses", SETTLEMENT: "Règlements", LOAN_PAYMENT: "Échéances d’emprunt", LOAN_FUNDING: "Déblocages d’emprunt", DEPRECIATION: "Dotations aux amortissements", OPENING: "À-nouveaux", INVENTORY: "Inventaire manuel" }).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select></label>
        </div></details>
        <ScreenStatus
          state={listView}
          onRetry={() => setRevision((value) => value + 1)}
          loading={<p>Chargement…</p>}
          empty={<p>Aucune écriture pour cette vue. {tab === "Journal" ? "Validées uniquement." : "Hors états comptables."}</p>}
        />
        {listVisible && <p>{count} écriture(s) · {tab === "Journal" ? "validées uniquement" : "hors états comptables"}</p>}
        {listVisible && entries.map((entry) => {
          const balanceId = `entry-${entry.id}-balance`;
          const reversalId = `entry-${entry.id}-reversal`;
          return <article className="entry-card" key={entry.id}>
          <h3>{entry.entry_number || "Brouillon #" + entry.id} · {entry.label}</h3>
          <p>{entry.accounting_date} · {entry.journal_code} · Pièce {entry.piece_reference}</p>
          <div className="ledger-table"><table><thead><tr><th>Compte</th><th>Libellé</th><th>Débit €</th><th>Crédit €</th></tr></thead><tbody>{entry.lines.map((line, i) => <tr key={i}><td>{line.account_number}</td><td>{line.label}</td><td>{line.debit}</td><td>{line.credit}</td></tr>)}</tbody><tfoot><tr><th colSpan={2}>{entry.balanced ? "Équilibrée" : "Déséquilibrée"}</th><td>{entry.total_debit}</td><td>{entry.total_credit}</td></tr></tfoot></table></div>
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
      {confirmation && <form className="entry-editor" onSubmit={(e) => {
        const data = formData(e); const { action, entry } = confirmation;
        void mutate(async () => {
          await request("/entries/" + entry.id + (action === "delete" ? "" : "/" + action), action === "delete" ? "DELETE" : "POST",
            action === "reverse" ? { accounting_date: data.get("date"), piece_reference: data.get("piece"), reason: data.get("reason") } : { expected_version: entry.version });
          setConfirmation(null);
        }, "Opération enregistrée.");
      }}>
        <h3>Confirmer : {confirmation.entry.label}</h3>
        <p>{confirmation.action === "validate" ? "La validation attribue un numéro définitif. Cette écriture ne pourra plus être modifiée ou supprimée." : confirmation.action === "delete" ? "Le brouillon sera supprimé. Son historique sera conservé." : "Une nouvelle écriture inversera les débits et crédits. L’écriture d’origine sera conservée."}</p>
        {confirmation.action === "reverse" && <>
          <label>Date de l’extourne<input name="date" type="date" required min={selectedYear?.start_date} max={selectedYear?.end_date} /></label>
          <label>Pièce de l’extourne<input name="piece" required /></label>
          <label>Motif<input name="reason" required minLength={5} maxLength={300} /></label>
        </>}
        <button disabled={busy}>Confirmer {confirmation.action === "validate" ? "la validation" : confirmation.action === "delete" ? "la suppression" : "l’extourne"}</button>
        <button type="button" onClick={() => setConfirmation(null)}>Annuler</button>
      </form>}
      {audit && <details open><summary>Historique de l’écriture</summary>{audit.map((item, i) => <div key={i}><strong>{item.action} · {item.timestamp}</strong><pre>{JSON.stringify(item.details, null, 2)}</pre></div>)}<button onClick={() => setAudit(null)}>Fermer l’historique</button></details>}
      {tab === "Balance" && <>
        <ScreenStatus state={listView} onRetry={() => setRevision((value) => value + 1)} loading={<p>Chargement…</p>} />
        {listVisible && balance && <div className="ledger-table"><table><caption>Balance générale · écritures validées</caption><thead><tr><th>Compte</th><th>Libellé</th><th>Total débit</th><th>Total crédit</th><th>Solde débiteur</th><th>Solde créditeur</th></tr></thead><tbody>{balance.balance.map((row) => <tr key={row.account_number}><td>{row.account_number}</td><td>{row.label}</td><td>{row.total_debit}</td><td>{row.total_credit}</td><td>{row.debit_balance}</td><td>{row.credit_balance}</td></tr>)}</tbody><tfoot><tr><th colSpan={2}>{balance.balanced ? "Balance équilibrée" : "ERREUR : balance déséquilibrée"}</th><td>{balance.total_debit}</td><td>{balance.total_credit}</td><td colSpan={2}>EUR</td></tr></tfoot></table></div>}
      </>}
      {tab === "Grand livre" && <>
        <label>Compte du grand livre<select value={account} onChange={(e) => { setAccount(e.target.value); setLedger([]); }}>{accounts.map((a) => <option key={a.number} value={a.number}>{a.number} · {a.label}</option>)}</select></label>
        <ScreenStatus
          state={listView}
          onRetry={() => setRevision((value) => value + 1)}
          loading={<p>Chargement…</p>}
          empty={<p>Aucune ligne dans ce grand livre.</p>}
        />
        {listVisible && <div className="ledger-table"><table><caption>Solde positif : débiteur · négatif : créditeur</caption><thead><tr><th>Date</th><th>Écriture</th><th>Libellé</th><th>Débit</th><th>Crédit</th><th>Solde</th></tr></thead><tbody>{ledger.map((line, i) => <tr key={i}><td>{line.date}</td><td>{line.entry_number}</td><td>{line.label}</td><td>{line.debit}</td><td>{line.credit}</td><td>{line.balance}</td></tr>)}</tbody></table></div>}
      </>}
      {tab === "Plan comptable" && <>
        <p>Le plan initial est configurable. Les libellés des comptes utilisés par des écritures validées sont figés.</p>
        <form onSubmit={(e) => {
          const data = formData(e);
          void mutate(() => request("/accounts", "POST", { number: data.get("number"), label: data.get("label"), account_type: data.get("kind") }), "Compte ajouté.");
        }}>
          <label>Numéro<input name="number" required pattern="[1-7][0-9]{2,9}" /></label>
          <label>Libellé du compte<input name="label" required /></label>
          <label>Type<select name="kind">{[["ASSET", "Actif"], ["LIABILITY", "Dette"], ["EQUITY", "Capitaux"], ["EXPENSE", "Charge"], ["INCOME", "Produit"]].map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
          <button disabled={busy}>Ajouter le compte</button>
        </form>
        <ul>{accounts.map((a) => <li key={a.number}>{a.number} · {a.label} · {a.active ? "Actif" : "Inactif"} <button disabled={busy} onClick={() => { void mutate(() => request("/accounts/" + a.number + "/active", "PATCH", { active: !a.active }), "Compte mis à jour."); }}>{a.active ? "Désactiver" : "Réactiver"} {a.number}</button></li>)}</ul>
      </>}
    </>}
  </section>
  </>;
}
