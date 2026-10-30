import { useEffect, useRef, useState } from "react";
import { request } from "../api/ledger";
import { describedBy, reopenCauses } from "./actionCauses";
import PrerequisiteList from "./PrerequisiteList";
import GlossaryTip from "./GlossaryTip";
import { GLOSSARY } from "./glossary";
import { SaveNoticeHost } from "./LocalFeedback";
import { useSaveNotice } from "./localFeedback";
import MutationStatus from "./MutationStatus";
import { useMutation } from "./useMutation";

const INVALIDATED = [
  "Les calculs fiscaux enregistrés pour cet exercice sont invalidés.",
  "Le snapshot liasse et les exports figés (FEC, dossier de contrôle) passent en SUPERSEDED ; les anciennes preuves restent consultables.",
  "L’exercice redevient ouvert : les écritures redeviennent modifiables et un nouveau calcul, pré-contrôle et clôture seront nécessaires pour regénérer les sorties.",
];

export default function ReopenYear({
  year,
  yearLabel,
  onExerciseTransition,
  locked = false,
}: {
  year: number;
  yearLabel?: string;
  onExerciseTransition?: () => void;
  locked?: boolean;
}) {
  const [confirmation, setConfirmation] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const { notice, show, dismiss } = useSaveNotice();
  const exerciseName = yearLabel ?? String(year);
  const { busy, step, run } = useMutation();
  const errorRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);

  const trimmedReason = reason.trim();
  const causes = busy || locked ? [] : reopenCauses(confirmation, reason);
  const causeId = "reopen-causes";
  const canSubmit = !busy && !locked && causes.length === 0;

  async function reopen() {
    if (!canSubmit) {
      if (confirmation !== "ROUVRIR") {
        setError("Saisissez exactement ROUVRIR pour confirmer.");
      } else if (trimmedReason.length < 10) {
        setError("Le motif doit comporter au moins 10 caractères.");
      }
      return;
    }
    await run(async (report) => {
      report("Réouverture de l’exercice…");
      setError("");
      dismiss();
      try {
        await request(
          `/years/${year}/reopen`,
          "POST",
          { confirmation: "ROUVRIR", reason: trimmedReason },
          "/api/filing",
        );
        show({
          kind: GLOSSARY.exercice.label,
          name: exerciseName,
          action: "rouvert",
          targetId: "reouvrir-exercice",
          detail: "Exercice rouvert. Recalculez la fiscalité avant un nouveau pré-contrôle.",
          next: { label: "Recalculer la fiscalité", href: "#calcul-fiscal" },
        });
        setConfirmation("");
        setReason("");
        onExerciseTransition?.();
      } catch (reasonError) {
        setError((reasonError as Error).message);
      }
    });
  }

  return (
    <div className="reopen-year" id="reouvrir-exercice" aria-labelledby="reopen-title">
      <SaveNoticeHost place="reouvrir-exercice" notice={notice} onDismiss={dismiss} />
      <div className="heading-with-help">
        <h4 id="reopen-title" tabIndex={-1}>Réouvrir l’exercice</h4>
        <GlossaryTip id="reouverture" />
      </div>
      <p>Réservé à une correction justifiée. L’action est tracée dans l’audit.</p>
      <ul aria-label="Effets de la réouverture">
        {INVALIDATED.map((item) => <li key={item}>{item}</li>)}
      </ul>
      <div className="form-grid">
        <label id="reopen-motif" tabIndex={-1}>
          Motif de la réouverture
          <textarea
            value={reason}
            rows={3}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Décrivez la correction à apporter (minimum 10 caractères)."
          />
        </label>
        <label id="reopen-confirmation" tabIndex={-1}>
          Confirmation — saisir ROUVRIR
          <input
            value={confirmation}
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => setConfirmation(event.target.value)}
            placeholder="ROUVRIR"
          />
        </label>
      </div>
      <MutationStatus step={step} />
      {error && <p role="alert" tabIndex={-1} ref={errorRef}>{error}</p>}
      <button type="button" disabled={!canSubmit} aria-busy={busy || undefined} aria-describedby={describedBy(causeId, causes)} onClick={() => { void reopen(); }}>
        {busy ? "Réouverture…" : "Réouvrir l’exercice"}
      </button>
      <PrerequisiteList id={causeId} causes={causes} />
    </div>
  );
}
