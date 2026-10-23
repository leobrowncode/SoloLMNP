import { useEffect, useMemo, useState, type ReactNode } from "react";
import { request } from "../api/ledger";
import LiasseSheet, { type Worksheet } from "./LiasseSheet";
import "./ledger.css";

interface Vintage {
  vintage: string;
  status: string;
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
  accounting_result: string;
  fiscal_result: string;
  deductible_depreciation: string;
  unused_depreciation: string;
  tax_loss: string;
  non_deductible: string;
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

function HelpTip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="help-tip">
      <button type="button" className="help-tip-btn" aria-label={`Aide : ${label}`}>?</button>
      <span role="tooltip" className="help-tip-panel">{children}</span>
    </span>
  );
}

function Metric({
  label, value, tip, accent,
}: {
  label: string; value: string; tip: string; accent?: "good" | "warn" | "neutral";
}) {
  return (
    <div className={`fiscal-metric fiscal-metric-${accent ?? "neutral"}`}>
      <dt>
        {label}
        <HelpTip label={label}>{tip}</HelpTip>
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
  const [result, setResult] = useState<Computation | null>(null);
  const [statements, setStatements] = useState<Statements | null>(null);
  const [worksheet, setWorksheet] = useState<Worksheet | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [adjustments, setAdjustments] = useState<AdjustmentDraft[]>([]);
  const [draft, setDraft] = useState<AdjustmentDraft>({
    account_number: "", amount: "", justification: "",
  });

  useEffect(() => {
    let current = true;
    void Promise.all([
      request<{ vintages: Vintage[] }>("/vintages", "GET", undefined, "/api/fiscal"),
      request<{ years: YearRow[] }>("/setup"),
    ]).then(([loaded, setup]) => {
      if (!current) return;
      setVintages(loaded.vintages);
      setYears(setup.years);
      setYear(setup.years.find((item) => item.status === "OPEN")?.id ?? setup.years[0]?.id ?? 0);
    }, (reason: Error) => { if (current) setError(reason.message); });
    return () => { current = false; };
  }, []);

  useEffect(() => {
    if (!year) return;
    let current = true;
    void request<Statements>(`/years/${year}/statements`).then((value) => {
      if (current) setStatements(value);
    }, (reason: Error) => { if (current) setError(reason.message); });
    return () => { current = false; };
  }, [year]);

  const chargeAccounts = useMemo(() => {
    const rows = statements?.income_statement.expenses ?? [];
    return rows.filter((row) => !row.account_number.startsWith("681") && row.amount !== "0.00");
  }, [statements]);

  const fiscalCents = result ? parseSigned(result.fiscal_result) : Number.NaN;
  const goalTone = !result || Number.isNaN(fiscalCents)
    ? "neutral"
    : fiscalCents === 0 ? "good" : fiscalCents > 0 ? "warn" : "neutral";

  async function compute() {
    setError("");
    setBusy(true);
    setWorksheet(null);
    try {
      const payload = {
        adjustments: adjustments.map((item) => ({
          account_number: item.account_number,
          amount: item.amount.replace(",", "."),
          justification: item.justification,
        })),
      };
      setResult(await request<Computation>(`/years/${year}`, "POST", payload, "/api/fiscal"));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
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

  const details = result?.details;
  const depUses = details?.prior_carry_forward_use?.depreciation ?? [];
  const lossUses = details?.prior_carry_forward_use?.tax_loss ?? [];

  return (
    <section className="ledger-page fiscal-dashboard" aria-labelledby="fiscal-title">
      <h2 id="fiscal-title">Charges & amortissements LMNP</h2>
      <p className="form-help">
        Le plafond d’amortissement vise un résultat fiscal proche de 0 €.
        La comptabilité ne change pas. Cession, TVA et plus-values restent hors de cet écran.
      </p>

      {error && <p className="ledger-error" role="alert">{error}</p>}

      <div className="toolbar fiscal-toolbar">
        <label>
          Exercice
          <HelpTip label="Exercice">
            Choisissez l’année ouverte à analyser. Les reports ne sont repris que depuis
            des exercices déjà clôturés.
          </HelpTip>
          <select
            value={year}
            onChange={(event) => {
              setYear(Number(event.target.value));
              setAdjustments([]);
              setStatements(null);
              setResult(null);
              setWorksheet(null);
            }}
          >
            {years.map((item) => (
              <option key={item.id} value={item.id}>
                {item.year}{item.status ? ` · ${item.status === "OPEN" ? "ouvert" : item.status === "CLOSED" ? "clôturé" : "prêt à clôturer"}` : ""}
              </option>
            ))}
          </select>
        </label>
        <button type="button" disabled={!year || busy} onClick={() => { void compute(); }}>
          {busy ? "Calcul…" : "Calculer le résultat fiscal"}
        </button>
        <button type="button" disabled={!year || busy} onClick={() => { void loadWorksheet(); }}>
          Liasse à recopier
        </button>
        <a href={year ? `/api/filing/years/${year}/fec` : undefined}>FEC (après clôture)</a>
      </div>

      <ul className="fiscal-rules-strip" aria-label="Règles LMNP utiles">
        <li>
          <strong>Plafond amortissement</strong>
          <HelpTip label="Plafond">
            L’amortissement déductible ne peut pas dépasser : loyers − autres charges
            déductibles. L’excédent est reporté, pas perdu.
          </HelpTip>
        </li>
        <li>
          <strong>Pas d’imputation revenu global</strong>
          <HelpTip label="Déficit">
            Un déficit LMNP se reporte sur les revenus LMNP des 10 années suivantes.
            Il ne diminue pas vos salaires ou autres revenus.
          </HelpTip>
        </li>
        <li>
          <strong>Terrain non amortissable</strong>
          <HelpTip label="Terrain">
            La part terrain doit être ventilée manuellement à l’achat. SoloLMNP refuse
            toute base amortissable sur un terrain.
          </HelpTip>
        </li>
      </ul>

      {statements && (
        <div className="fiscal-panel">
          <h3>
            1. Loyers & charges comptabilisés
            <HelpTip label="Loyers et charges">
              Issus du ledger validé (hors centralisation). Ce sont les montants
              comptables, avant retraitement fiscal.
            </HelpTip>
          </h3>
          <dl className="fiscal-metrics">
            <Metric
              label="Loyers / produits"
              value={statements.income_statement.total_income}
              tip="Total des comptes de produits (classe 7) de l’exercice."
            />
            <Metric
              label="Charges totales"
              value={statements.income_statement.total_expenses}
              tip="Toutes les charges comptables, y compris la dotation 681."
            />
            <Metric
              label="Résultat comptable"
              value={statements.income_statement.result}
              tip="Produits − charges au ledger. Différent du résultat fiscal LMNP."
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
          <HelpTip label="Réintégration">
            Si une charge n’est que partiellement déductible (ex. usage privé), indiquez
            ici la part à réintégrer. L’écriture comptable reste entière ; seule la
            fiscalité change. Les comptes 681 (amortissements) ne se gèrent pas ici.
          </HelpTip>
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
          <button type="button" disabled={!year || busy} onClick={() => { void loadSuggestions(); }}>
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
            <HelpTip label="Capacité">
              Capacité = loyers − charges déductibles (hors dotation). On déduit d’abord
              l’amortissement de l’année dans cette limite, puis les reports antérieurs
              (FIFO) sur le reste de capacité.
            </HelpTip>
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
                <HelpTip label="Capacité calculée">
                  Maximum d’amortissement fiscalement déductible cette année. Au-delà,
                  le surplus est reporté.
                </HelpTip>
              </span>
              <strong>{details.capacity ?? "—"} €</strong>
            </li>
            <li>
              <span>Dotation comptable 681</span>
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
              <span>Amortissement non déduit (report N)</span>
              <strong>{result.unused_depreciation} €</strong>
            </li>
            <li>
              <span>− Imputation déficits antérieurs</span>
              <strong>{details.prior_tax_loss_used ?? "0.00"} €</strong>
            </li>
            <li className={`fiscal-waterfall-result fiscal-waterfall-${goalTone}`}>
              <span>
                Résultat fiscal
                <HelpTip label="Résultat fiscal">
                  Montant BIC de l’activité après plafond et reports. Cible usuelle : 0 €
                  (pas d’impôt BIC supplémentaire via cette activité).
                </HelpTip>
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
              tip="Reste au ledger. Le fiscal ne le réécrit jamais."
            />
            <Metric
              label="Amortissement déductible total"
              value={result.deductible_depreciation}
              tip="Dotation de l’année dans la capacité + reprises de reports."
              accent="good"
            />
            <Metric
              label="Stock amortissement reporté"
              value={result.unused_depreciation}
              tip="Excédent de l’année, utilisable plus tard si capacité."
            />
            <Metric
              label="Déficit LMNP de l’exercice"
              value={result.tax_loss}
              tip="Si résultat fiscal négatif. Report 10 ans, hors revenu global."
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

          <p className="field-hint">
            {result.declarable
              ? "Ce résultat peut alimenter la liasse. Aucune télétransmission."
              : "Aperçu fiscal. La liasse indique ensuite si elle est recopiable. Aucune télétransmission."}
          </p>
        </div>
      )}

      {worksheet && <LiasseSheet worksheet={worksheet} yearId={year} />}

      <details className="fiscal-panel">
        <summary>Millésimes chargés (technique)</summary>
        <ul>
          {vintages.map((item) => (
            <li key={item.vintage}>
              Millésime {item.vintage} · {item.status} · périmètre LMNP
              {item.blocked.length ? ` · règles bloquées : ${item.blocked.join(", ")}` : ""}
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
