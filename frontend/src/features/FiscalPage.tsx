import { useEffect, useState } from "react";
import { request } from "../api/ledger";

interface Vintage { vintage: string; status: string; blocked: string[]; executable: string[] }
interface Computation {
  status: string; declarable: boolean; accounting_result: string; fiscal_result: string;
  unused_depreciation: string; tax_loss: string; non_deductible: string;
}
interface Worksheet {
  transmission: boolean; disclaimer: string;
  personal_return: { form: string; official_case: string | null; status: string; amount: string };
}

export default function FiscalPage() {
  const [vintages, setVintages] = useState<Vintage[]>([]);
  const [year, setYear] = useState(0);
  const [years, setYears] = useState<{ id: number; year: number }[]>([]);
  const [result, setResult] = useState<Computation | null>(null);
  const [worksheet, setWorksheet] = useState<Worksheet | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let current = true;
    void Promise.all([
      request<{ vintages: Vintage[] }>("/vintages", "GET", undefined, "/api/fiscal"),
      request<{ years: { id: number; year: number }[] }>("/setup"),
    ]).then(([loaded, setup]) => {
      if (!current) return;
      setVintages(loaded.vintages);
      setYears(setup.years);
      setYear(setup.years[0]?.id ?? 0);
    }, (reason: Error) => { if (current) setError(reason.message); });
    return () => { current = false; };
  }, []);
  async function compute() {
    setError(""); setResult(null);
    try {
      setResult(await request<Computation>(`/years/${year}`, "POST", { adjustments: [] }, "/api/fiscal"));
    } catch (reason) { setError((reason as Error).message); }
  }
  async function loadWorksheet() {
    setError(""); setWorksheet(null);
    try {
      setWorksheet(await request<Worksheet>(`/years/${year}/efi`, "GET", undefined, "/api/filing"));
    } catch (reason) { setError((reason as Error).message); }
  }
  return <section className="ledger-page" aria-labelledby="fiscal-title">
    <h2 id="fiscal-title">Aperçu fiscal</h2>
    <p>Retraitement séparé du ledger. Statut recherche uniquement : aucun montant n’est déclarable et aucune case n’est télédéclarée.</p>
    {error && <p role="alert">{error}</p>}
    <ul>{vintages.map((item) => <li key={item.vintage}>Millésime {item.vintage} · {item.status} · règles bloquées : {item.blocked.join(", ") || "aucune"}</li>)}</ul>
    {years.length > 0 && <div className="toolbar">
      <label>Exercice <select value={year} onChange={(event) => { setYear(Number(event.target.value)); setResult(null); }}>{years.map((item) => <option key={item.id} value={item.id}>{item.year}</option>)}</select></label>
      <button type="button" onClick={() => { void compute(); }}>Calculer l’aperçu</button>
      <button type="button" onClick={() => { void loadWorksheet(); }}>Afficher la feuille EFI</button>
    </div>}
    {worksheet && <div aria-live="polite">
      <h3>Feuille de recopie</h3>
      <p>{worksheet.disclaimer}</p>
      <p>Télétransmission : {worksheet.transmission ? "oui" : "non"}.</p>
      <p>{worksheet.personal_return.form} · case officielle : {worksheet.personal_return.official_case ?? "non vérifiée"} · statut {worksheet.personal_return.status} · montant de travail {worksheet.personal_return.amount} €.</p>
    </div>}
    {result && <div aria-live="polite">
      <p>Statut : {result.status}. Déclarable : {result.declarable ? "oui" : "non"}.</p>
      <p>Résultat comptable : {result.accounting_result} € · Résultat fiscal : {result.fiscal_result} €</p>
      <p>Amortissement non déduit : {result.unused_depreciation} € · Déficit LMNP : {result.tax_loss} €</p>
      <p>Réintégrations : {result.non_deductible} €. Le revenu global n’est pas imputé.</p>
    </div>}
  </section>;
}
