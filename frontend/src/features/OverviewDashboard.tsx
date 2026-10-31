import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { fetchDashboard, dashboardFailure, type DashboardPayload, type DashboardStep, type DashboardStepId } from "../api/dashboard";
import { MOBILE_QUERY, useMediaQuery } from "../lib/viewport";
import { formatCents } from "../lib/format";
import DossierProgress from "./DossierProgress";
import DossierStatus from "./DossierStatus";
import GlossaryTip from "./GlossaryTip";
import { presentStep } from "./overviewCards";
import PrerequisiteList from "./PrerequisiteList";
import ScreenStatus from "./ScreenStatus";
import { useScreenQuery } from "./useScreenQuery";
import type { GlossaryId } from "./glossary";

const STEP_HELP: Record<DashboardStepId, GlossaryId> = {
  structure: "siren",
  operations: "loyers-charges",
  assets: "amortissement",
  opening: "a-nouveaux",
  closing: "cloture",
  filing: "liasse",
};

const AMOUNT_LABEL: Partial<Record<DashboardStepId, string>> = {
  operations: "Montant des opérations",
  assets: "Dotations comptabilisées",
  opening: "Montant des à-nouveaux",
  filing: "Résultat fiscal",
};

function formatWhen(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function DossierZone({ data, compact }: { data: DashboardPayload; compact: boolean }) {
  const status = <DossierStatus dossier={data.dossier} />;
  const progress = <DossierProgress progression={data.progression} />;
  const context = compact ? (
    <details className="dossier-fold">
      <summary>Statut et progression</summary>
      <div className="dossier-context">
        {status}
        {progress}
      </div>
    </details>
  ) : (
    <div className="dossier-context">
      {status}
      {progress}
    </div>
  );
  return (
    <div className="dashboard-next dossier-zone">
      {context}
      <Link className="dashboard-continue" to={data.continue.href} aria-describedby="dashboard-next">
        Continuer
      </Link>
      <p id="dashboard-next">{data.continue.detail}</p>
    </div>
  );
}

function StepCard({ step, data }: { step: DashboardStep; data: DashboardPayload }) {
  const view = presentStep(step, {
    sharedSummary: data.progression.summary,
    currentStep: data.progression.current_step,
  });
  const amountLabel = AMOUNT_LABEL[step.id];
  return (
    <li
      className={`dashboard-step dashboard-step-${step.status}`}
      data-step={step.id}
      data-step-status={step.status}
    >
      <div className="heading-with-help">
        <h3>{step.label}</h3>
        <GlossaryTip id={STEP_HELP[step.id]} />
      </div>
      <p className="dashboard-state">
        <strong>{view.statusLabel}</strong>
        {view.summary ? ` · ${view.summary}` : null}
      </p>
      {amountLabel && step.amount_cents !== null && (
        <p className="dashboard-amount">
          {amountLabel} : <strong>{formatCents(BigInt(step.amount_cents))}</strong>
        </p>
      )}
      {view.showEvent && step.last_event && (
        <p className="dashboard-event">
          Dernier événement : {step.last_event.label}
          {" · "}
          <time dateTime={step.last_event.occurred_at}>{formatWhen(step.last_event.occurred_at)}</time>
        </p>
      )}
      {view.actions.length > 0 && (
        <ul className="dashboard-actions">
          {view.actions.map((action) => (
            <li key={`${action.href}-${action.label}`}>
              <a href={action.href}>{action.label}</a>
            </li>
          ))}
        </ul>
      )}
      <PrerequisiteList id={`${step.id}-prerequisites`} causes={view.missing} intro="Il manque :" />
    </li>
  );
}

function Board({ data }: { data: DashboardPayload }) {
  return (
    <ol className="dashboard-steps" aria-label="Étapes du dossier">
      {data.steps.map((step) => <StepCard key={step.id} step={step} data={data} />)}
    </ol>
  );
}

export default function OverviewDashboard({ lead = null }: { lead?: ReactNode }) {
  const compact = useMediaQuery(MOBILE_QUERY);
  const { state, retry } = useScreenQuery(fetchDashboard, "dashboard", {
    keepPrevious: true,
    isEmpty: (data) => data.steps.length === 0,
    mapError: dashboardFailure,
  });
  const board = state.phase === "loaded" ? state.data : null;
  return (
    <>
      {board && <DossierZone data={board} compact={compact} />}
      {lead}
      <section className="dashboard-board" aria-labelledby="dashboard-title" data-screen-phase={state.phase}>
        <div className="section-heading">
          <h2 id="dashboard-title">Tableau de bord du dossier</h2>
        </div>
        <ScreenStatus
          state={state}
          onRetry={retry}
          loading={<p className="notice">Chargement du dossier…</p>}
          empty={<p className="notice">Aucun dossier à afficher.</p>}
        />
        {board && <Board data={board} />}
      </section>
    </>
  );
}
