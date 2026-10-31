import { useEffect, useRef, useState } from "react";
import { request } from "../api/ledger";
import { closeConfirmCauses, closePrepareCauses, describedBy, precheckAction, warningKey, warningsAcknowledged } from "./actionCauses";
import { sameStatusClaim, type ExportStatus } from "./exportStatus";
import PrerequisiteList from "./PrerequisiteList";
import GlossaryTip from "./GlossaryTip";
import { GLOSSARY } from "./glossary";
import { SaveNoticeHost } from "./LocalFeedback";
import { useSaveNotice } from "./localFeedback";
import ReopenYear from "./ReopenYear";
import MutationStatus from "./MutationStatus";
import { useMutation } from "./useMutation";

interface Notice {
  code: string;
  message: string;
}

interface Check {
  blocking: boolean;
  year_status?: string;
  output_status?: string;
  output_label?: string;
  exports?: ExportStatus["exports"];
  errors: Notice[];
  warnings: Notice[];
  infos?: Notice[];
}

export default function CloseYear({
  year,
  yearStatus,
  yearLabel,
  onExerciseTransition,
}: {
  year: number;
  yearStatus?: string;
  yearLabel?: string;
  onExerciseTransition?: () => void;
}) {
  const [check, setCheck] = useState<Check | null>(null);
  const [error, setError] = useState("");
  const { notice, show, dismiss } = useSaveNotice();
  const exerciseName = yearLabel ?? String(year);
  const [acks, setAcks] = useState<string[]>([]);
  const [prepared, setPrepared] = useState(false);
  const [closed, setClosed] = useState(false);
  const [seenStatus, setSeenStatus] = useState(yearStatus);
  const errorRef = useRef<HTMLParagraphElement>(null);
  const { busy, step, run } = useMutation();
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  // Reopen (#33) reports OPEN through the shared exercise status. Drop the
  // ceremony of the previous close so this screen can start again.
  if (yearStatus !== seenStatus) {
    setSeenStatus(yearStatus);
    if (yearStatus === "OPEN") {
      setClosed(false);
      setPrepared(false);
      setAcks([]);
      setCheck(null);
      dismiss();
      setError("");
    }
  }

  const sealed = closed || yearStatus === "CLOSED" || check?.year_status === "CLOSED";
  const canPrepare = check !== null
    && !check.blocking
    && !sealed
    && warningsAcknowledged(check.warnings, acks);
  const prepareCauses = check ? closePrepareCauses({
    sealed, blocking: check.blocking, errors: check.errors, warnings: check.warnings, acks,
  }) : [];
  const confirmCauses = check ? closeConfirmCauses({
    prepared, sealed, blocking: Boolean(check.blocking), errors: check.errors,
  }) : [];
  const prepareCauseId = "close-prepare-causes";
  const confirmCauseId = "close-confirm-causes";

  async function load() {
    await run(async (report) => {
      report("Pré-contrôle de l’exercice…");
      setError("");
      try {
        const next = await request<Check>(`/years/${year}/precheck`, "GET", undefined, "/api/filing");
        setCheck(next);
        setAcks([]);
        setPrepared(false);
        setClosed(next.year_status === "CLOSED");
        dismiss();
      } catch (reason) {
        setError((reason as Error).message);
      }
    });
  }

  async function ready() {
    if (!canPrepare) return;
    await run(async (report) => {
      report("Préparation de la clôture…");
      setError("");
      dismiss();
      try {
        const next = await request<Check>(
          `/years/${year}/ready`, "POST", { acknowledged: acks }, "/api/filing",
        );
        const kept = acks.filter((token) => next.warnings.some((item) => warningKey(item) === token));
        const accepted = !next.blocking
          && next.year_status !== "CLOSED"
          && warningsAcknowledged(next.warnings, kept);
        setCheck(next);
        setAcks(kept);
        setPrepared(accepted);
        setClosed(next.year_status === "CLOSED");
        if (!accepted) {
          setError("Le pré-contrôle a changé. Accusez les avertissements affichés.");
          onExerciseTransition?.();
          return;
        }
        show({
          kind: GLOSSARY.exercice.label,
          name: exerciseName,
          action: "préparé",
          targetId: "confirmer-cloture",
          detail: "Exercice marqué prêt à clôturer. La confirmation suivante fige les écritures.",
          next: { label: "Confirmer la clôture", href: "#confirmer-cloture" },
        });
        onExerciseTransition?.();
      } catch (reason) {
        setError((reason as Error).message);
      }
    });
  }

  async function closeYear() {
    if (!prepared || sealed || check?.blocking) return;
    await run(async (report) => {
      report("Clôture de l’exercice…");
      setError("");
      dismiss();
      try {
        await request(`/years/${year}/close`, "POST", { confirmation: "CLOTURER" }, "/api/filing");
        setClosed(true);
        show({
          kind: GLOSSARY.exercice.label,
          name: exerciseName,
          action: "clôturé",
          targetId: "confirmer-cloture",
          detail: "Exercice clôturé. Les exports déjà figés restent consultables.",
          next: { label: "Voir les sorties figées", href: "#sorties-figees" },
        });
        onExerciseTransition?.();
      } catch (reason) {
        setError((reason as Error).message);
      }
    });
  }

  function toggle(code: string, checked: boolean) {
    setAcks((current) => (
      checked
        ? (current.includes(code) ? current : [...current, code])
        : current.filter((item) => item !== code)
    ));
  }

  return <section aria-labelledby="close-title">
    <div className="heading-with-help">
      <h3 id="close-title" tabIndex={-1}>Pré-contrôle et clôture</h3>
      <GlossaryTip id="pre-controle" />
      <GlossaryTip id="cloture" />
    </div>
    <p>Le pré-contrôle vient après le calcul fiscal. Il bloque sur une erreur. Chaque avertissement affiché doit être accusé ; un nouveau pré-contrôle efface les cases précédentes. La réouverture ultérieure exige un motif et invalide les exports.</p>
    <button type="button" disabled={busy} aria-busy={busy || undefined} onClick={() => { void load(); }}>Lancer le pré-contrôle</button>
    <MutationStatus step={step} />
    {error && <p role="alert" tabIndex={-1} ref={errorRef}>{error}</p>}
    <div id="confirmer-cloture">
    <SaveNoticeHost place="confirmer-cloture" notice={notice} onDismiss={dismiss} />
    {check && <div>
      {check.output_label && (
        <p className={`fiscal-output-status fiscal-output-${check.output_status ?? "recherche"}`}>
          <strong>{check.output_label}</strong>
          {sameStatusClaim(check) && (
            <span>Même statut pour le calcul, la liasse et les exports.</span>
          )}
        </p>
      )}
      {(check.infos ?? []).map((item) => <p key={warningKey(item)}>{item.message}</p>)}
      {check.errors.map((item) => {
        const action = precheckAction(item.code);
        return <p key={`${item.code}-${item.message}`} role="alert">{item.message} <a href={action.href}>{action.label}</a></p>;
      })}
      {check.warnings.map((item) => {
        const token = warningKey(item);
        return <label key={token}><input type="checkbox" disabled={busy} checked={acks.includes(token)} onChange={(event) => toggle(token, event.target.checked)} />{item.message}</label>;
      })}
      <button id="close-prepare" type="button" disabled={!canPrepare || busy} aria-busy={busy || undefined} aria-describedby={describedBy(prepareCauseId, prepareCauses)} onClick={() => { void ready(); }}>Accuser et préparer la clôture</button>
      <PrerequisiteList id={prepareCauseId} causes={prepareCauses} />
      <button type="button" disabled={!prepared || Boolean(check.blocking) || sealed || busy} aria-busy={busy || undefined} aria-describedby={describedBy(confirmCauseId, confirmCauses)} onClick={() => { void closeYear(); }}>Confirmer la clôture</button>
      <PrerequisiteList id={confirmCauseId} causes={confirmCauses} />
    </div>}
    </div>
    {sealed && (
      <ReopenYear
        year={year}
        yearLabel={exerciseName}
        locked={busy}
        {...(onExerciseTransition ? { onExerciseTransition } : {})}
      />
    )}
  </section>;
}
