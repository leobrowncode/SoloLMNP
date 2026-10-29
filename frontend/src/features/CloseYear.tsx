import { useEffect, useRef, useState } from "react";
import { request } from "../api/ledger";
import ReopenYear from "./ReopenYear";

interface Notice {
  code: string;
  message: string;
}

interface Check {
  blocking: boolean;
  year_status?: string;
  errors: Notice[];
  warnings: Notice[];
  infos?: Notice[];
}

const FISCAL_FIX_CODES = new Set(["FISCAL_NOT_COMPUTED", "FISCAL_STALE"]);

function acknowledgedExactly(warnings: Notice[], acks: string[]) {
  const expected = new Set(warnings.map((item) => item.code));
  return acks.length === expected.size && acks.every((code) => expected.has(code));
}

export default function CloseYear({
  year,
  yearStatus,
  onExerciseTransition,
}: {
  year: number;
  yearStatus?: string;
  onExerciseTransition?: () => void;
}) {
  const [check, setCheck] = useState<Check | null>(null);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState("");
  const [acks, setAcks] = useState<string[]>([]);
  const [prepared, setPrepared] = useState(false);
  const [closed, setClosed] = useState(false);
  const [seenStatus, setSeenStatus] = useState(yearStatus);
  const errorRef = useRef<HTMLParagraphElement>(null);
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
      setReceipt("");
      setError("");
    }
  }

  const sealed = closed || yearStatus === "CLOSED" || check?.year_status === "CLOSED";
  const canPrepare = check !== null
    && !check.blocking
    && !sealed
    && acknowledgedExactly(check.warnings, acks);

  async function load() {
    setError("");
    try {
      const next = await request<Check>(`/years/${year}/precheck`, "GET", undefined, "/api/filing");
      setCheck(next);
      setAcks([]);
      setPrepared(false);
      setClosed(next.year_status === "CLOSED");
      setReceipt("");
    } catch (reason) {
      setError((reason as Error).message);
    }
  }

  async function ready() {
    if (!canPrepare) return;
    setError("");
    setReceipt("");
    try {
      const next = await request<Check>(
        `/years/${year}/ready`, "POST", { acknowledged: acks }, "/api/filing",
      );
      const kept = acks.filter((code) => next.warnings.some((item) => item.code === code));
      const accepted = !next.blocking
        && next.year_status !== "CLOSED"
        && acknowledgedExactly(next.warnings, kept);
      setCheck(next);
      setAcks(kept);
      setPrepared(accepted);
      setClosed(next.year_status === "CLOSED");
      if (!accepted) {
        setError("Le pré-contrôle a changé. Accusez les avertissements affichés.");
        onExerciseTransition?.();
        return;
      }
      setReceipt("Exercice marqué prêt à clôturer. La confirmation suivante fige les écritures.");
      onExerciseTransition?.();
    } catch (reason) {
      setError((reason as Error).message);
    }
  }

  async function closeYear() {
    if (!prepared || sealed || check?.blocking) return;
    setError("");
    setReceipt("");
    try {
      await request(`/years/${year}/close`, "POST", { confirmation: "CLOTURER" }, "/api/filing");
      setClosed(true);
      setReceipt("Exercice clôturé. Les exports déjà figés restent consultables.");
      onExerciseTransition?.();
    } catch (reason) {
      setError((reason as Error).message);
    }
  }

  function toggle(code: string, checked: boolean) {
    setAcks((current) => (
      checked
        ? (current.includes(code) ? current : [...current, code])
        : current.filter((item) => item !== code)
    ));
  }

  return <section aria-labelledby="close-title">
    <h3 id="close-title">Pré-contrôle et clôture</h3>
    <p>Le pré-contrôle vient après le calcul fiscal. Il bloque sur une erreur. Chaque avertissement affiché doit être accusé ; un nouveau pré-contrôle efface les cases précédentes. La réouverture ultérieure exige un motif et invalide les exports.</p>
    <button type="button" onClick={() => { void load(); }}>Lancer le pré-contrôle</button>
    {error && <p role="alert" tabIndex={-1} ref={errorRef}>{error}</p>}
    {receipt && <p role="status">{receipt}</p>}
    {check && <div>
      {(check.infos ?? []).map((item) => <p key={item.code}>{item.message}</p>)}
      {check.errors.map((item) => <p key={`${item.code}-${item.message}`} role="alert">{item.message}{FISCAL_FIX_CODES.has(item.code) && <> <a href="#calcul-fiscal">Calculer le résultat fiscal</a></>}</p>)}
      {check.warnings.map((item) => <label key={item.code}><input type="checkbox" checked={acks.includes(item.code)} onChange={(event) => toggle(item.code, event.target.checked)} />{item.message}</label>)}
      <button type="button" disabled={!canPrepare} onClick={() => { void ready(); }}>Accuser et préparer la clôture</button>
      <button type="button" disabled={!prepared || Boolean(check.blocking) || sealed} onClick={() => { void closeYear(); }}>Confirmer la clôture</button>
    </div>}
    {sealed && (
      <ReopenYear
        year={year}
        {...(onExerciseTransition ? { onExerciseTransition } : {})}
      />
    )}
  </section>;
}
