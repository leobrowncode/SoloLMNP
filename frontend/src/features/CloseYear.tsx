import { useEffect, useRef, useState } from "react";
import { request } from "../api/ledger";

interface Check {
  blocking: boolean;
  errors: { code: string; message: string }[];
  warnings: { code: string; message: string }[];
  infos?: { code: string; message: string }[];
}

const FISCAL_FIX_CODES = new Set(["FISCAL_NOT_COMPUTED", "FISCAL_STALE"]);

export default function CloseYear({ year }: { year: number }) {
  const [check, setCheck] = useState<Check | null>(null);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState("");
  const [acks, setAcks] = useState<string[]>([]);
  const [prepared, setPrepared] = useState(false);
  const errorRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  async function load() {
    setError(""); setReceipt(""); setCheck(null);
    try { setCheck(await request<Check>(`/years/${year}/precheck`, "GET", undefined, "/api/filing")); }
    catch (reason) { setError((reason as Error).message); }
  }
  async function ready() {
    if (!check) return;
    setError("");
    try {
      const next = await request<Check>(`/years/${year}/ready`, "POST", { acknowledged: acks }, "/api/filing");
      setCheck(next);
      setPrepared(true);
      setReceipt("Exercice marqué prêt à clôturer. La confirmation suivante fige les écritures.");
    } catch (reason) { setError((reason as Error).message); }
  }
  async function closeYear() {
    setError("");
    try {
      await request(`/years/${year}/close`, "POST", { confirmation: "CLOTURER" }, "/api/filing");
      setReceipt("Exercice clôturé. Les exports déjà figés restent consultables.");
    } catch (reason) { setError((reason as Error).message); }
  }
  return <section aria-labelledby="close-title">
    <h3 id="close-title">Pré-contrôle et clôture</h3>
    <p>Le pré-contrôle vient après le calcul fiscal. Il bloque sur une erreur. Chaque avertissement doit être accusé. La réouverture ultérieure exige un motif et invalide les exports.</p>
    <button type="button" onClick={() => { void load(); }}>Lancer le pré-contrôle</button>
    {error && <p role="alert" tabIndex={-1} ref={errorRef}>{error}</p>}
    {receipt && <p role="status">{receipt}</p>}
    {check && <div>
      {(check.infos ?? []).map((item) => <p key={item.code}>{item.message}</p>)}
      {check.errors.map((item) => <p key={`${item.code}-${item.message}`} role="alert">{item.message}{FISCAL_FIX_CODES.has(item.code) && <> <a href="#calcul-fiscal">Calculer le résultat fiscal</a></>}</p>)}
      {check.warnings.map((item) => <label key={item.code}><input type="checkbox" checked={acks.includes(item.code)} onChange={(event) => setAcks((current) => event.target.checked ? [...current, item.code] : current.filter((code) => code !== item.code))} />{item.message}</label>)}
      <button type="button" disabled={check.blocking} onClick={() => { void ready(); }}>Accuser et préparer la clôture</button>
      <button type="button" disabled={!prepared || check.blocking} onClick={() => { void closeYear(); }}>Confirmer la clôture</button>
    </div>}
  </section>;
}
