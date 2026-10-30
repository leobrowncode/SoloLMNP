import type { DossierStatus as Dossier } from "../api/status";
import { DOSSIER_HINTS } from "./dossierStatus";

export default function DossierStatus({ dossier }: { dossier: Dossier }) {
  return (
    <div className={`dossier-status dossier-status-${dossier.status}`} data-dossier={dossier.status}>
      <p>
        <span className="dossier-kicker">Statut dossier</span>{" "}
        <strong>{dossier.label}</strong>
        {dossier.year !== null && <span> · exercice {dossier.year}</span>}
      </p>
      <p className="dossier-hint">{DOSSIER_HINTS[dossier.status]}</p>
    </div>
  );
}
