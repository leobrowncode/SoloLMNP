import { Link } from "react-router-dom";
import { dashboardFailure, fetchDashboard } from "../api/dashboard";
import { useScreenQuery } from "./useScreenQuery";

export default function DossierProgress() {
  const { state, retry } = useScreenQuery(fetchDashboard, "dossier-progress", {
    mapError: dashboardFailure,
  });
  if (state.phase === "error") {
    return (
      <div className="dossier-progress" data-progression="unavailable">
        <p className="dossier-hint">Progression indisponible.</p>
        <button type="button" onClick={retry}>Réessayer la progression</button>
      </div>
    );
  }
  if (state.phase !== "loaded" || state.data === null || state.data.steps.length === 0 || state.data.progression.total === 0) {
    return null;
  }
  const data = state.data;
  const progress = data.progression;
  return (
    <div
      className={`dossier-progress dossier-progress-${progress.current_status}`}
      data-progression={progress.label}
      role="region"
      aria-label="Progression du dossier"
    >
      <p>
        <span className="dossier-kicker">Progression</span>{" "}
        <strong>{progress.label}</strong>
        <span> · {progress.current_label}</span>
        <span> · {progress.current_status_label}</span>
      </p>
      <p className="dossier-hint">{progress.summary}</p>
      <Link to={data.continue.href}>{data.continue.label}</Link>
    </div>
  );
}
