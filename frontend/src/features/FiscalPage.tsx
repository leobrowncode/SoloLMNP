import { useEffect, useMemo, useRef, useState } from "react";
import { RequestError, request } from "../api/ledger";
import { useUnsavedGuard } from "../routing/useUnsavedGuard";
import { describedBy, fiscalActionCauses } from "./actionCauses";
import CloseYear from "./CloseYear";
import GlossaryTip from "./GlossaryTip";
import type { GlossaryId } from "./glossary";
import HelpTip from "./HelpTip";
import PrerequisiteList from "./PrerequisiteList";
import ExportDownloads from "./ExportDownloads";
import { asExportStatus, type ExportStatus } from "./exportStatus";
import ScreenStatus from "./ScreenStatus";
import {
  beginLoad, defer, emptyView, failLoad, finishLoad, idleView, showsData, toApiError, type ScreenView,
} from "./screenState";
import LiasseSheet, { type Worksheet } from "./LiasseSheet";
import { calculationNotice, outputLabel, outputTrust } from "./outputStatus";
import "./ledger.css";

interface Vintage {
  vintage: string;
  status: string;
  output_status?: string;
  output_label?: string;
  blocked: string[];
  scope?: string[];
  executable: string[];
}
interface YearRow { id: number; year: number; status?: string }
interface ReportRow {
  origin_year: number;
  opening: string;
  used: string;
  remaining_after: string;
}
interface DepreciationCategory {
  label: string;
  base: string;
  rate_percent: string;
  annual_max: string;
}
interface CarryUse {
  origin_year: number;
  used: string;
  remaining_after: string;
}
interface Computation {
  status: string;
  declarable: boolean;
  output_status?: string;
  output_label?: string;
  accounting_result: string;
  fiscal_result: string;
  deductible_depreciation: string;
  unused_depreciation: string;
  tax_loss: string;
  non_deductible: string;
  computed_at?: string;
  invalidated?: boolean;
  ledger_sha256?: string;
  current_ledger_sha256?: string;
  structuring_sha256?: string | null;
  current_structuring_sha256?: string | null;
  details?: {
    prior_carry_forward_use?: {
      status: string;
      depreciation?: CarryUse[];
      tax_loss?: CarryUse[];
      tax_loss_horizon_years?: number;
      notes?: string;
    };
    prior_depreciation_available?: string;
    prior_tax_loss_available?: string;
    depreciation_reports?: ReportRow[];
    depreciation_categories?: DepreciationCategory[];
    prior_depreciation_used?: string;
    prior_tax_loss_used?: string;
    operating_income?: string;
    other_charges?: string;
    accounting_depreciation?: string;
    capacity?: string;
    current_deductible_depreciation?: string;
    fiscal_result_before_prior_losses?: string;
    goal_hint?: string;
    additions?: { account_number: string; amount: string; justification: string }[];
  };
}
interface StatementRow { account_number: string; label: string; amount: string }
interface Statements {
  income_statement: {
    income: StatementRow[];
    expenses: StatementRow[];
    total_income: string;
    total_expenses: string;
    result: string;
  };
}
interface AdjustmentDraft {
  account_number: string;
  amount: string;
  justification: string;
}

function Metric({
  label, value, help, accent,
}: {
  label: string; value: string; help: GlossaryId; accent?: "good" | "warn" | "neutral";
}) {
  return (
    <div className={`fiscal-metric fiscal-metric-${accent ?? "neutral"}`}>
      <dt>
        {label}
        <GlossaryTip id={help} label={label} />
      </dt>
      <dd>{value} €</dd>
    </div>
  );
}

function parseSigned(value: string): number {
  const normalized = value.replace(",", ".");
  if (!/^-?\d+(?:\.\d{1,2})?$/.test(normalized)) return Number.NaN;
  const [whole = "0", fraction = ""] = normalized.replace("-", "").split(".");
  const cents = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return normalized.startsWith("-") ? -cents : cents;
}

function formatComputedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", {
    timeZone: "Europe/Paris",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function hashMoved(stored: string, current: string): boolean {
  return stored.length === 64 && current.length === 64 && stored !== current;
}

function Freshness({ result }: { result: Computation }) {
  const stored = result.ledger_sha256 ?? "";
  const current = result.current_ledger_sha256 ?? "";
  const comparable = stored.length === 64 && current.length === 64;
  const obsolete = result.invalidated === true
    || (comparable && stored !== current)
    || hashMoved(result.structuring_sha256 ?? "", result.current_structuring_sha256 ?? "");
  if (!result.computed_at && !stored) return null;
  return (
    <p className={`fiscal-freshness${obsolete ? " fiscal-freshness-obsolete" : ""}`}>
      {result.computed_at && (
        <span>
          Calcul du <time dateTime={result.computed_at}>{formatComputedAt(result.computed_at)}</time>
        </span>
      )}
      {stored && <span className="fiscal-fingerprint">Empreinte {stored}</span>}
      {obsolete && <strong>Obsolète</strong>}
      {comparable && !obsolete && <span>Correspond au ledger</span>}
    </p>
  );
}

function euros(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(Math.round(cents));
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

function projectDotation(dotation: number, base: number, priorDep: number, priorLoss: number) {
  const capacity = Math.max(0, base);
  const current = Math.min(Math.max(0, dotation), capacity);
  const priorDepUsed = Math.min(Math.max(0, priorDep), capacity - current);
  const unused = Math.max(0, dotation - current);
  const beforeLoss = base - current - priorDepUsed;
  const lossUsed = Math.min(Math.max(0, priorLoss), Math.max(0, beforeLoss));
  return { capacity, current, priorDepUsed, unused, fiscal: beforeLoss - lossUsed };
}

function ZeroCockpit({
  income, charges, additions, booked, priorDep, priorLoss, reports, categories,
}: {
  income: number;
  charges: number;
  additions: number;
  booked: number;
  priorDep: number;
  priorLoss: number;
  reports: ReportRow[];
  categories: DepreciationCategory[];
}) {
  const base = income - charges + additions;
  const ceiling = Math.max(0, base);
  const upper = Math.max(booked, ceiling);
  const [dotation, setDotation] = useState(booked);
  const view = projectDotation(dotation, base, priorDep, priorLoss);
  const fill = view.capacity === 0 ? 0 : Math.min(100, Math.round((view.current / view.capacity) * 100));
  const simulated = dotation !== booked;
  let reading = "Déplacez le curseur pour voir l’effet sur le résultat. Les écritures ne changent pas.";
  if (!simulated && view.fiscal === 0 && view.unused > 0) {
    reading = `Objectif atteint : 0 €. ${euros(view.unused)} € d’amortissement partent en report.`;
  } else if (!simulated && view.fiscal === 0) {
    reading = "Objectif atteint : 0 €, et rien à reporter.";
  } else if (view.fiscal > 0) {
    reading = `Il reste ${euros(view.fiscal)} €. Une dotation de ${euros(view.capacity)} € met le résultat à 0 €.`;
  } else if (view.fiscal < 0) {
    reading = `Déficit de ${euros(-view.fiscal)} €, reporté sur les LMNP suivants. Ajouter de l’amortissement ne l’augmente pas.`;
  }
  const stockRows: { year: number; opening: number; used: number; remaining: number }[] = [];
  let left = view.priorDepUsed;
  for (const row of reports) {
    const opening = parseSigned(row.opening);
    const used = Math.min(Math.max(0, opening), Math.max(0, left));
    left -= used;
    stockRows.push({ year: row.origin_year, opening, used, remaining: opening - used });
  }

  return (
    <div className="zero-cockpit">
      <p className="zero-kicker">Objectif : 0 €</p>
      <p className={`zero-figure zero-figure-${view.fiscal === 0 ? "good" : "warn"}`}>
        {euros(view.fiscal)} €
      </p>
      <p>{reading}</p>
      <div className="cap-track" aria-hidden="true">
        <span className="cap-fill" style={{ width: `${fill}%` }} />
      </div>
      <p className="cap-caption">
        Plafond {euros(view.capacity)} € · déduit {euros(view.current)} € · reporté {euros(view.unused)} €
      </p>
      {upper > 0 && (
        <label className="dotation-slider">
          Dotation de l’année
          <input
            type="range"
            min={0}
            max={upper}
            step={100}
            value={dotation}
            onChange={(event) => setDotation(Number(event.target.value))}
          />
          <input
            inputMode="decimal"
            value={euros(dotation)}
            onChange={(event) => {
              const next = parseSigned(event.target.value);
              if (!Number.isNaN(next)) setDotation(Math.min(upper, Math.max(0, next)));
            }}
          />
        </label>
      )}
      <p className="field-hint">
        Comptabilisé : {euros(booked)} €. Le curseur simule une autre dotation.
        Pour la changer vraiment, ajustez les durées dans Immobilisations.
        {simulated ? " Les écritures actuelles ne sont pas modifiées." : ""}
      </p>
      <h3>Par catégorie</h3>
      <ul className="cap-cats">
        {categories.length === 0 && (
          <li>Aucune immobilisation. Les plafonds apparaîtront après le registre.</li>
        )}
        {categories.map((row) => (
          <li key={`${row.label}-${row.base}`}>
            <span>{row.label}</span>
            <span>
              {row.rate_percent.replace(".", ",")} % / an
              {" · "}
              max {row.annual_max} €
            </span>
          </li>
        ))}
      </ul>
      <h3>Reports d’amortissement</h3>
      <p className="field-hint">Les plus anciens sont repris en premier, dans la limite du plafond.</p>
      <ul className="report-list">
        {stockRows.length === 0 && <li>Aucun report des années précédentes.</li>}
        {stockRows.map((row) => (
          <li key={row.year}>
            {row.year} : stock {euros(row.opening)} € · repris {euros(row.used)} € · reste {euros(row.remaining)} €
          </li>
        ))}
        <li>Cette année : {euros(view.unused)} € à reporter</li>
        {priorLoss > 0 && <li>Déficits LMNP en stock : {euros(priorLoss)} €</li>}
      </ul>
    </div>
  );
}

export default function FiscalPage() {
  const [vintages, setVintages] = useState<Vintage[]>([]);
  const [year, setYear] = useState(0);
  const [years, setYears] = useState<YearRow[]>([]);
  const refreshToken = useRef(0);
  const resultEpoch = useRef(0);
  const [result, setResult] = useState<Computation | null>(null);
  const [statements, setStatements] = useState<Statements | null>(null);
  const [worksheet, setWorksheet] = useState<Worksheet | null>(null);
  const [exportView, setExportView] = useState<ScreenView<{ yearId: number; status: ExportStatus }>>(idleView());
  const [exportTick, setExportTick] = useState(0);
  const [boot, setBoot] = useState<ScreenView<{ ready: true }>>(() => beginLoad(idleView(), false));
  const [bootAttempt, setBootAttempt] = useState(0);
  const [statementsView, setStatementsView] = useState<ScreenView<Statements>>(idleView());
  const [statementsAttempt, setStatementsAttempt] = useState(0);
  const [resultView, setResultView] = useState<ScreenView<Computation>>(idleView());
  const [resultAttempt, setResultAttempt] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [adjustments, setAdjustments] = useState<AdjustmentDraft[]>([]);
  const [draft, setDraft] = useState<AdjustmentDraft>({
    account_number: "", amount: "", justification: "",
  });
  const fiscalDraftDirty = adjustments.length > 0
    || draft.account_number.trim() !== ""
    || draft.amount.trim() !== ""
    || draft.justification.trim() !== "";
  useUnsavedGuard(fiscalDraftDirty);

  useEffect(() => {
    let current = true;
    defer(() => {
      if (!current) return;
      setBoot((previous) => beginLoad(previous, previous.data !== null));
    });
    void Promise.all([
      request<{ vintages: Vintage[] }>("/vintages", "GET", undefined, "/api/fiscal"),
      request<{ years: YearRow[] }>("/setup"),
    ]).then(([loaded, setup]) => {
      if (!current) return;
      setVintages(loaded.vintages);
      setYears(setup.years);
      setYear(setup.years.find((item) => item.status === "OPEN")?.id ?? setup.years[0]?.id ?? 0);
      setBoot(finishLoad({ ready: true }));
    }, (reason: unknown) => {
      if (current) setBoot((previous) => failLoad(previous, toApiError(reason), previous.data !== null));
    });
    return () => { current = false; };
  }, [bootAttempt]);

  useEffect(() => {
    let current = true;
    if (!year) {
      defer(() => {
        if (current) setStatementsView(idleView());
      });
      return () => { current = false; };
    }
    defer(() => {
      if (!current) return;
      setStatements(null);
      setStatementsView((previous) => beginLoad(previous, false));
    });
    void request<Statements>(`/years/${year}/statements`).then((value) => {
      if (!current) return;
      setStatements(value);
      setStatementsView(finishLoad(value));
    }, (reason: unknown) => {
      if (!current) return;
      setStatements(null);
      setStatementsView((previous) => failLoad(previous, toApiError(reason), false));
    });
    return () => { current = false; };
  }, [year, statementsAttempt]);

  useEffect(() => {
    let current = true;
    if (!year) {
      defer(() => {
        if (current) setExportView(idleView());
      });
      return () => { current = false; };
    }
    const selected = year;
    defer(() => {
      if (!current) return;
      setExportView((previous) => beginLoad(previous, previous.data?.yearId === selected));
    });
    void request<unknown>(`/years/${selected}/exports`, "GET", undefined, "/api/filing").then((value) => {
      if (!current) return;
      const parsed = asExportStatus(value);
      if (!parsed) {
        setExportView((previous) => failLoad(previous, {
          code: "EXPORTS_UNAVAILABLE",
          message: "Les sorties n’ont pas pu être lues.",
        }, previous.data?.yearId === selected));
        return;
      }
      setExportView(finishLoad({ yearId: selected, status: parsed }));
    }, (reason: unknown) => {
      if (!current) return;
      setExportView((previous) => failLoad(
        previous,
        toApiError(reason),
        previous.data?.yearId === selected,
      ));
    });
    return () => { current = false; };
  }, [year, exportTick]);

  useEffect(() => {
    let current = true;
    if (!year) {
      defer(() => {
        if (current) setResultView(idleView());
      });
      return () => { current = false; };
    }
    const epoch = resultEpoch.current;
    defer(() => {
      if (!current) return;
      setResultView((previous) => beginLoad(previous, false));
    });
    void request<Computation>(`/years/${year}`, "GET", undefined, "/api/fiscal").then((value) => {
      if (!(current && resultEpoch.current === epoch)) return;
      setResult(value);
      setResultView(finishLoad(value));
    }, (reason: unknown) => {
      if (!current || resultEpoch.current !== epoch) return;
      setResult(null);
      if (reason instanceof RequestError && reason.status === 404) {
        setResultView(emptyView());
        return;
      }
      setResultView((previous) => failLoad(previous, toApiError(reason), false));
    });
    return () => { current = false; };
  }, [year, resultAttempt]);

  const chargeAccounts = useMemo(() => {
    const rows = statements?.income_statement.expenses ?? [];
    return rows.filter((row) => !row.account_number.startsWith("681") && row.amount !== "0.00");
  }, [statements]);

  const fiscalCents = result?.fiscal_result ? parseSigned(result.fiscal_result) : Number.NaN;
  const goalTone = !result || Number.isNaN(fiscalCents)
    ? "neutral"
    : fiscalCents === 0 ? "good" : fiscalCents > 0 ? "warn" : "neutral";

  async function compute() {
    const epoch = ++resultEpoch.current;
    setError("");
    setBusy(true);
    setWorksheet(null);
    setResult(null);
    setResultView((previous) => beginLoad(previous, false));
    try {
      const payload = {
        adjustments: adjustments.map((item) => ({
          account_number: item.account_number,
          amount: item.amount.replace(",", "."),
          justification: item.justification,
        })),
      };
      const next = await request<Computation>(`/years/${year}`, "POST", payload, "/api/fiscal");
      if (resultEpoch.current === epoch) {
        setResult(next);
        setResultView(finishLoad(next));
      }
      setExportTick((tick) => tick + 1);
    } catch (reason) {
      if (resultEpoch.current !== epoch) return;
      setResult(null);
      setResultView(idleView());
      setError(reason instanceof Error ? reason.message : "Calcul fiscal refusé.");
    } finally {
      if (resultEpoch.current === epoch) setBusy(false);
    }
  }

  async function loadWorksheet() {
    setError("");
    setBusy(true);
    try {
      setWorksheet(await request<Worksheet>(`/years/${year}/efi`, "GET", undefined, "/api/filing"));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function chooseYear(next: number) {
    refreshToken.current += 1;
    resultEpoch.current += 1;
    setBusy(false);
    setYear(next);
    setAdjustments([]);
    setStatements(null);
    setResult(null);
    setWorksheet(null);
  }

  async function refreshExercise() {
    setExportTick((tick) => tick + 1);
    const token = refreshToken.current;
    const epoch = resultEpoch.current;
    const selected = year;
    const hadWorksheet = worksheet !== null;
    const hadResult = result !== null;
    const current = () => refreshToken.current === token;
    const failures: string[] = [];
    const setupTask = request<{ years: YearRow[] }>("/setup").then((setup) => {
      if (!current()) return;
      setYears(setup.years);
      setYear((currentId) => (
        currentId && setup.years.some((item) => item.id === currentId)
          ? currentId
          : setup.years.find((item) => item.status === "OPEN")?.id ?? setup.years[0]?.id ?? 0
      ));
    }, (reason: Error) => { failures.push(reason.message); });
    const statementTask = selected
      ? request<Statements>(`/years/${selected}/statements`).then((value) => {
        if (!current()) return;
        setStatements(value);
        setStatementsView(finishLoad(value));
      }, (reason: unknown) => {
        if (!current()) return;
        setStatements(null);
        setStatementsView((previous) => failLoad(previous, toApiError(reason), false));
      })
      : Promise.resolve();
    const worksheetTask = selected && hadWorksheet
      ? request<Worksheet>(`/years/${selected}/efi`, "GET", undefined, "/api/filing").then((value) => {
        if (current()) setWorksheet(value);
      }, (reason: Error) => {
        if (current()) setWorksheet(null);
        failures.push(reason.message);
      })
      : Promise.resolve();
    const resultTask = selected && hadResult
      ? request<Computation>(`/years/${selected}`, "GET", undefined, "/api/fiscal").then((value) => {
        if (!(current() && resultEpoch.current === epoch)) return;
        setResult(value);
        setResultView(finishLoad(value));
      }, (reason: unknown) => {
        if (!current() || resultEpoch.current !== epoch) return;
        setResult(null);
        if (reason instanceof RequestError && reason.status === 404) {
          setResultView(emptyView());
          return;
        }
        setResultView((previous) => failLoad(previous, toApiError(reason), false));
      })
      : Promise.resolve();
    await Promise.all([setupTask, statementTask, worksheetTask, resultTask]);
    if (!current()) return;
    const message = failures[0];
    if (message) setError(message);
    else setError("");
  }

  async function loadSuggestions() {
    setError("");
    setBusy(true);
    try {
      const rows = await request<AdjustmentDraft[]>(
        `/years/${year}/reintegrations`, "GET", undefined, "/api/fiscal",
      );
      if (rows.length === 0) {
        setError("Aucune part non déductible n’est saisie sur les dépenses de cet exercice.");
        return;
      }
      setAdjustments((current) => {
        const known = new Set(current.map((item) => item.account_number));
        return [
          ...current,
          ...rows.filter((item) => !known.has(item.account_number)),
        ];
      });
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function addAdjustment() {
    setError("");
    if (!draft.account_number) {
      setError("Choisissez le compte de charge à réintégrer.");
      return;
    }
    if (!/^\d+(?:[.,]\d{1,2})?$/.test(draft.amount.trim())) {
      setError("Indiquez la quote-part non déductible au centime près.");
      return;
    }
    if (draft.justification.trim().length < 10) {
      setError("La justification doit faire au moins 10 caractères.");
      return;
    }
    if (adjustments.some((item) => item.account_number === draft.account_number)) {
      setError("Ce compte est déjà dans la liste des réintégrations.");
      return;
    }
    setAdjustments((current) => [...current, {
      account_number: draft.account_number,
      amount: draft.amount.trim().replace(",", "."),
      justification: draft.justification.trim(),
    }]);
    setDraft({ account_number: "", amount: "", justification: "" });
  }

  const selectedYear = years.find((item) => item.id === year);
  const fiscalCauses = fiscalActionCauses(year, years);
  const fiscalCauseId = "fiscal-year-causes";
  const details = result?.details;
  const depUses = details?.prior_carry_forward_use?.depreciation ?? [];
  const lossUses = details?.prior_carry_forward_use?.tax_loss ?? [];

  return (
    <section className="ledger-page fiscal-dashboard" aria-labelledby="fiscal-title" data-screen-phase={boot.phase}>
      <h2 id="fiscal-title">Charges & amortissements LMNP</h2>
        <p className="form-help">
        Le plafond d’amortissement vise un résultat fiscal proche de 0 €.
        La comptabilité ne change pas. Cession, TVA et plus-values restent hors de cet écran.
        Ordre de fin d’exercice : calcul fiscal, pré-contrôle, clôture, puis liasse et FEC figés.
      </p>
      <div className="heading-with-help">
        <GlossaryTip id="cession" />
        <GlossaryTip id="liasse" />
        <GlossaryTip id="fec" />
        <GlossaryTip id="efi" />
      </div>

      {error && <p className="ledger-error" role="alert">{error}</p>}
      <ScreenStatus
        state={boot}
        onRetry={() => setBootAttempt((value) => value + 1)}
        loading={<p role="status">Chargement de la fiscalité…</p>}
      />
      <ScreenStatus
        state={statementsView}
        onRetry={() => setStatementsAttempt((value) => value + 1)}
        loading={<p role="status">Chargement des données comptables…</p>}
      />
      <ScreenStatus
        state={resultView}
        onRetry={() => setResultAttempt((value) => value + 1)}
        empty={<p>Aucun calcul fiscal n’est enregistré pour cet exercice.</p>}
      />

      <div className="toolbar fiscal-toolbar">
        <label>
          Exercice
          <GlossaryTip id="exercice" />
          <select
            value={year}
            onChange={(event) => { chooseYear(Number(event.target.value)); }}
          >
            {years.map((item) => (
              <option key={item.id} value={item.id}>
                {item.year}{item.status ? ` · ${item.status === "OPEN" ? "ouvert" : item.status === "CLOSED" ? "clôturé" : "prêt à clôturer"}` : ""}
              </option>
            ))}
          </select>
        </label>
        <button id="calcul-fiscal" type="button" disabled={!year || busy} aria-describedby={describedBy(fiscalCauseId, fiscalCauses)} onClick={() => { void compute(); }}>
          {busy ? "Calcul…" : "Calculer le résultat fiscal"}
        </button>
        <PrerequisiteList id={fiscalCauseId} causes={fiscalCauses} />
      </div>

      <ul className="fiscal-rules-strip" aria-label="Règles LMNP utiles">
        <li>
          <strong>Plafond amortissement</strong>
          <GlossaryTip id="plafond" />
        </li>
        <li>
          <strong>Pas d’imputation revenu global</strong>
          <GlossaryTip id="deficit" />
        </li>
        <li>
          <strong>Terrain non amortissable</strong>
          <GlossaryTip id="terrain" />
        </li>
      </ul>

      {statements && (
        <div className="fiscal-panel">
          <h3>
            1. Loyers & charges comptabilisés
            <GlossaryTip id="loyers-charges" />
          </h3>
          <dl className="fiscal-metrics">
            <Metric
              label="Loyers / produits"
              value={statements.income_statement.total_income}
              help="produits"
            />
            <Metric
              label="Charges totales"
              value={statements.income_statement.total_expenses}
              help="charges"
            />
            <Metric
              label="Résultat comptable"
              value={statements.income_statement.result}
              help="resultat-comptable"
            />
          </dl>
          <div className="ledger-table">
            <table>
              <caption>Détail des charges (hors lecture fiscale)</caption>
              <thead>
                <tr>
                  <th>Compte</th>
                  <th>Libellé</th>
                  <th>Montant (€)</th>
                  <th>Rôle LMNP</th>
                </tr>
              </thead>
              <tbody>
                {statements.income_statement.expenses.map((row) => (
                  <tr key={row.account_number}>
                    <td>{row.account_number}</td>
                    <td>{row.label}</td>
                    <td>{row.amount}</td>
                    <td>
                      {row.account_number.startsWith("681")
                        ? "Dotation — plafonnée fiscalement"
                        : "Charge — déductible sauf réintégration"}
                    </td>
                  </tr>
                ))}
                {statements.income_statement.expenses.length === 0 && (
                  <tr><td colSpan={4}>Aucune charge validée pour cet exercice.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="fiscal-panel">
        <h3>
          2. Quote-part de charge non déductible
          <GlossaryTip id="reintegration" />
        </h3>
        <p className="field-hint">
          Optionnel. Chaque réintégration augmente la capacité d’amortissement déductible
          (loyers − charges déductibles).
        </p>
        <div className="form-grid">
          <label>
            Compte de charge
            <HelpTip label="Compte">Compte de charge hors 681, déjà présent au ledger.</HelpTip>
            <select
              value={draft.account_number}
              onChange={(event) => setDraft({ ...draft, account_number: event.target.value })}
            >
              <option value="">Choisir…</option>
              {chargeAccounts.map((row) => (
                <option key={row.account_number} value={row.account_number}>
                  {row.account_number} · {row.label} ({row.amount} €)
                </option>
              ))}
            </select>
          </label>
          <label className="field-money">
            Part non déductible (€)
            <HelpTip label="Montant">
              Montant à réintégrer, plafonné par le solde du compte. Format 12.34.
            </HelpTip>
            <input
              inputMode="decimal"
              value={draft.amount}
              onChange={(event) => setDraft({ ...draft, amount: event.target.value })}
              placeholder="0.00"
            />
          </label>
          <label>
            Justification
            <HelpTip label="Justification">
              Motif court et traçable (minimum 10 caractères), conservé dans le calcul.
            </HelpTip>
            <input
              value={draft.justification}
              onChange={(event) => setDraft({ ...draft, justification: event.target.value })}
              placeholder="Ex. quote-part usage privé confirmée"
            />
          </label>
        </div>
        <div className="form-actions">
          <button type="button" onClick={addAdjustment}>Ajouter la réintégration</button>
          <button type="button" disabled={!year || busy} aria-describedby={describedBy(fiscalCauseId, fiscalCauses)} onClick={() => { void loadSuggestions(); }}>
            Reprendre les parts non déductibles saisies
          </button>
        </div>
        {adjustments.length > 0 && (
          <ul className="fiscal-adjustment-list">
            {adjustments.map((item) => (
              <li key={item.account_number}>
                <span>{item.account_number} · {item.amount} € — {item.justification}</span>
                <button
                  type="button"
                  onClick={() => setAdjustments((rows) => rows.filter((row) => row.account_number !== item.account_number))}
                >
                  Retirer
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {result && details && (
        <div className="fiscal-panel" aria-live="polite">
          <Freshness result={result} />
          <ZeroCockpit
            key={`${details.accounting_depreciation ?? "0"}-${details.capacity ?? "0"}`}
            income={parseSigned(details.operating_income ?? "0")}
            charges={parseSigned(details.other_charges ?? "0")}
            additions={parseSigned(result.non_deductible)}
            booked={parseSigned(details.accounting_depreciation ?? "0")}
            priorDep={parseSigned(details.prior_depreciation_available ?? "0")}
            priorLoss={parseSigned(details.prior_tax_loss_available ?? "0")}
            reports={details.depreciation_reports ?? []}
            categories={details.depreciation_categories ?? []}
          />
          <h3>
            3. Capacité & amortissements
            <GlossaryTip id="capacite" />
          </h3>
          <ol className="fiscal-waterfall">
            <li>
              <span>Loyers / produits</span>
              <strong>{details.operating_income ?? "—"} €</strong>
            </li>
            <li>
              <span>− Autres charges (hors 681)</span>
              <strong>{details.other_charges ?? "—"} €</strong>
            </li>
            <li>
              <span>+ Réintégrations</span>
              <strong>{result.non_deductible} €</strong>
            </li>
            <li className="fiscal-waterfall-key">
              <span>
                = Capacité d’amortissement
                <GlossaryTip id="capacite" label="Capacité calculée" />
              </span>
              <strong>{details.capacity ?? "—"} €</strong>
            </li>
            <li>
              <span><span>Dotation comptable 681</span> <GlossaryTip id="compte-681" /></span>
              <strong>{details.accounting_depreciation ?? "—"} €</strong>
            </li>
            <li>
              <span>Dont déductible cette année</span>
              <strong>{details.current_deductible_depreciation ?? "—"} €</strong>
            </li>
            <li>
              <span>+ Reprise reports amortissement</span>
              <strong>{details.prior_depreciation_used ?? "0.00"} €</strong>
            </li>
            <li>
              <span><span>Amortissement non déduit (report N)</span> <GlossaryTip id="report-amortissement" /></span>
              <strong>{result.unused_depreciation} €</strong>
            </li>
            <li>
              <span>− Imputation déficits antérieurs</span>
              <strong>{details.prior_tax_loss_used ?? "0.00"} €</strong>
            </li>
            <li className={`fiscal-waterfall-result fiscal-waterfall-${goalTone}`}>
              <span>
                <span>Résultat fiscal</span>
                <GlossaryTip id="resultat-fiscal" />
              </span>
              <strong>{result.fiscal_result} €</strong>
            </li>
          </ol>

          <div className={`fiscal-goal fiscal-goal-${goalTone}`}>
            <p><strong>Lecture rapide</strong></p>
            <p>{details.goal_hint}</p>
          </div>

          <dl className="fiscal-metrics">
            <Metric
              label="Résultat comptable"
              value={result.accounting_result}
              help="resultat-comptable"
            />
            <Metric
              label="Amortissement déductible total"
              value={result.deductible_depreciation}
              help="amortissement"
              accent="good"
            />
            <Metric
              label="Stock amortissement reporté"
              value={result.unused_depreciation}
              help="report-amortissement"
            />
            <Metric
              label="Déficit LMNP de l’exercice"
              value={result.tax_loss}
              help="deficit"
            />
          </dl>

          {(depUses.length > 0 || lossUses.length > 0) && (
            <div className="ledger-table">
              <table>
                <caption>Reports antérieurs consommés (FIFO)</caption>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Exercice d’origine</th>
                    <th>Repris (€)</th>
                    <th>Reste après (€)</th>
                  </tr>
                </thead>
                <tbody>
                  {depUses.map((item) => (
                    <tr key={`dep-${item.origin_year}`}>
                      <td>Amortissement non déduit</td>
                      <td>{item.origin_year}</td>
                      <td>{item.used}</td>
                      <td>{item.remaining_after}</td>
                    </tr>
                  ))}
                  {lossUses.map((item) => (
                    <tr key={`loss-${item.origin_year}`}>
                      <td>Déficit LMNP</td>
                      <td>{item.origin_year}</td>
                      <td>{item.used}</td>
                      <td>{item.remaining_after}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className={`fiscal-output-status fiscal-output-${outputTrust(result)}`}>
            <strong>{outputLabel(result)}</strong>
            <span>{calculationNotice(outputTrust(result))}</span>
          </p>
        </div>
      )}

      {year !== 0 && (
        <div className="fiscal-panel">
          <CloseYear
            key={year}
            year={year}
            {...(selectedYear?.status !== undefined ? { yearStatus: selectedYear.status } : {})}
            onExerciseTransition={() => { void refreshExercise(); }}
          />
        </div>
      )}

      <div className="fiscal-panel" id="sorties-figees">
        <h3>Sorties figées</h3>
        <p className="field-hint">
          Aucun envoi n’est effectué. Chaque sortie indique Provisoire, Bloquée ou Finale.
          Une sortie bloquée liste ses prérequis et ne se télécharge pas. Le refus reste sur cette page.
        </p>
        <div className="toolbar">
          <button type="button" disabled={!year || busy} aria-describedby={describedBy(fiscalCauseId, fiscalCauses)} onClick={() => { void loadWorksheet(); }}>
            Liasse à recopier
          </button>
        </div>
        {year !== 0 && (
          <ScreenStatus
            state={exportView}
            onRetry={() => setExportTick((tick) => tick + 1)}
            loading={<p role="status">Chargement des sorties…</p>}
          />
        )}
        {year !== 0 && showsData(exportView) && exportView.data.yearId === year && (
          <ExportDownloads yearId={year} status={exportView.data.status} />
        )}
      </div>
      {worksheet && <LiasseSheet worksheet={worksheet} />}

      <div className="heading-with-help">
        <GlossaryTip id="millesime" />
      </div>
      <details className="fiscal-panel">
        <summary>Millésimes chargés (technique)</summary>
        <ul>
          {boot.phase === "loaded" && vintages.length === 0 && <li>Aucun millésime chargé.</li>}
          {vintages.map((item) => (
            <li key={item.vintage}>
              Millésime {item.vintage} · {item.output_label ?? "Recherche"} · périmètre LMNP
              {item.blocked.length ? ` · règles bloquées : ${item.blocked.join(", ")}` : ""}
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
