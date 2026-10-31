import type { DashboardProgression } from "../api/dashboard";

export default function DossierProgress({ progression }: { progression: DashboardProgression }) {
  if (progression.total === 0) return null;
  return (
    <div
      className={`dossier-progress dossier-progress-${progression.current_status}`}
      data-progression={progression.label}
      role="region"
      aria-label="Progression du dossier"
    >
      <p>
        <span className="dossier-kicker">Progression</span>{" "}
        <strong>{progression.label}</strong>
        <span> · {progression.current_label}</span>
        <span> · {progression.current_status_label}</span>
      </p>
    </div>
  );
}
