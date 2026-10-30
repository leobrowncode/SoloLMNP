import { Link } from "react-router-dom";
import { fetchDashboard, dashboardFailure, type DashboardPayload, type DashboardStep, type DashboardStepId } from "../api/dashboard";
import GlossaryTip from "./GlossaryTip";
import PrerequisiteList from "./PrerequisiteList";
import ScreenStatus from "./ScreenStatus";
import { useScreenQuery } from "./useScreenQuery";
import type { GlossaryId } from "./glossary";
import { formatCents } from "../lib/format";

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

function StepCard({ step }: { step: DashboardStep }) {
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
        <span className="dossier-kicker">État</span> <strong>{step.status_label}</strong>
      </p>
      <p>{step.summary}</p>
      {amountLabel && step.amount_cents !== null && (
        <p className="dashboard-amount">
          {amountLabel} : <strong>{formatCents(BigInt(step.amount_cents))}</strong>
        </p>
      )}
      {step.last_event ? (
        <p className="dashboard-event">
          Dernier événement : {step.last_event.label}
          {" · "}
          <time dateTime={step.last_event.occurred_at}>{formatWhen(step.last_event.occurred_at)}</time>
        </p>
      ) : (
        <p className="dashboard-event">Aucun événement utile pour l’instant.</p>
      )}
      <PrerequisiteList id={`${step.id}-prerequisites`} causes={step.prerequisites} intro="Il manque :" />
    </li>
  );
}

function Board({ data }: { data: DashboardPayload }) {
  return (
    <>
      <div className="dashboard-next">
        <Link className="dashboard-continue" to={data.continue.href} aria-describedby="dashboard-next">
          Continuer
        </Link>
        <p id="dashboard-next">{data.continue.detail}</p>
      </div>
      <ol className="dashboard-steps" aria-label="Étapes du dossier">
        {data.steps.map((step) => <StepCard key={step.id} step={step} />)}
      </ol>
    </>
  );
}

export default function OverviewDashboard() {
  const { state, retry } = useScreenQuery(fetchDashboard, "dashboard", {
    keepPrevious: true,
    isEmpty: (data) => data.steps.length === 0,
    mapError: dashboardFailure,
  });
  const board = state.phase === "loaded" ? state.data : null;
  return (
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
  );
}
