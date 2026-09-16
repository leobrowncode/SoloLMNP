import { useEffect, useRef, useState } from "react";
import { assetsRequest as api, type Asset, type DepreciationPeriod } from "../api/assets";
import { request, type Account, type Setup } from "../api/ledger";
import { operationsRequest, type Property } from "../api/operations";
import ReviewForm, { type Field } from "./ReviewForm";
import "./ledger.css";

interface Editor { title: string; path: string; fields: Field[]; retry?: boolean; }
const categories: [string, string][] = [
  ["BUILDING", "Construction"], ["FURNITURE", "Mobilier"], ["EQUIPMENT", "Équipement"],
  ["IMPROVEMENT", "Travaux immobilisés"], ["OTHER", "Autre immobilisation"],
];

export default function AssetsPage() {
  const [setup, setSetup] = useState<Setup | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [periods, setPeriods] = useState<DepreciationPeriod[]>([]);
  const [yearId, setYearId] = useState(0);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const periodRequest = useRef(0);

  useEffect(() => {
    let active = true;
    void Promise.all([
      request<Setup>("/setup"), request<Account[]>("/accounts"),
      operationsRequest<Property[]>("/properties"), api<Asset[]>(""),
    ]).then(([s, a, p, rows]) => {
      if (!active) return;
      setSetup(s); setAccounts(a); setProperties(p); setAssets(rows);
      setYearId((value) => value || s.years.find((year) => year.status === "OPEN")?.id || 0);
    }).catch((reason: Error) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [revision]);
  useEffect(() => {
    if (!yearId) return;
    let active = true;
    const requestId = ++periodRequest.current;
    void api<DepreciationPeriod[]>(`/years/${yearId}/periods`).then((rows) => {
      if (active && requestId === periodRequest.current) setPeriods(rows);
    }).catch((reason: Error) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [yearId, revision]);

  const account = (name: string, label: string, prefix: string, value?: string): Field => ({
    name, label, value, choices: accounts.filter((row) => row.active && row.number.startsWith(prefix)).map((row) => [row.number, `${row.number} · ${row.label}`]),
  });
  const property: Field = { name: "property_id", label: "Bien", choices: properties.map((row) => [String(row.id), row.name]) };
  function openAsset(land: boolean) {
    setEditor({ title: land ? "Inscrire un terrain non amortissable" : "Inscrire une immobilisation", path: "", fields: [
      property,
      { name: "category", label: "Catégorie", choices: land ? [["LAND", "Terrain — jamais amorti"]] : categories },
      { name: "label", label: "Libellé" },
      { name: "acquisition_date", label: "Date d’acquisition", type: "date" },
      { name: "service_start_date", label: "Date de mise en service", type: "date" },
      { name: "acquisition_value", label: "Valeur d’acquisition (€)", money: true },
      { name: "depreciable_value", label: "Valeur amortissable (€)", money: true, value: land ? "0.00" : undefined },
      { name: "non_depreciable_value", label: "Valeur non amortissable (€)", money: true, value: land ? undefined : "0.00" },
      { name: "residual_value", label: "Valeur résiduelle (€)", money: true, value: "0.00" },
      { name: "method", label: "Méthode", choices: land ? [["NONE", "Aucune — terrain"]] : [["LINEAR", "Linéaire"]] },
      { name: "useful_life_months", label: "Durée d’utilisation en mois", type: "number", optional: land },
      account("asset_account", "Compte d’immobilisation", "2", land ? "211000" : undefined),
      { ...account("depreciation_account", "Compte d’amortissement", "28"), optional: land },
      { name: "basis_reason", label: "Justification de la valeur (au moins 5 caractères)" },
      { name: "duration_reason", label: "Justification de la durée (au moins 5 caractères)", value: land ? "Terrain non amortissable" : undefined },
    ] });
  }
  function openComponent(asset: Asset) {
    setEditor({ title: `Ajouter un composant à ${asset.label}`, path: `/${asset.id}/components`, fields: [
      { name: "category", label: "Catégorie technique" }, { name: "label", label: "Libellé" },
      { name: "value", label: "Valeur du composant (€)", money: true },
      { name: "useful_life_months", label: "Durée d’utilisation en mois", type: "number" },
      { name: "service_start_date", label: "Date de mise en service", type: "date" },
      account("asset_account", "Compte d’immobilisation", "2", asset.asset_account),
      account("depreciation_account", "Compte d’amortissement", "28", asset.depreciation_account ?? undefined),
      { name: "basis_reason", label: "Justification de la ventilation" },
      { name: "duration_reason", label: "Justification de la durée" },
    ] });
  }
  async function save(data: Record<string, unknown>) {
    if (!editor) return;
    await api(editor.path, "POST", data);
    setEditor(null); setMessage("Enregistrement effectué."); setRevision((value) => value + 1);
  }
  async function calculate() {
    setError(""); setMessage("");
    const requestId = ++periodRequest.current;
    try {
      const rows = await api<DepreciationPeriod[]>(`/years/${yearId}/calculate`, "POST");
      if (requestId === periodRequest.current) {
        setPeriods(rows); setMessage(`${rows.length} période(s) calculée(s). Vérifiez-les avant comptabilisation.`);
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Calcul impossible."); }
  }

  return <section id="assets" className="ledger-page" aria-labelledby="assets-title">
    <p className="eyebrow">REGISTRE ET SOUS-LEDGER</p><h2 id="assets-title">Immobilisations & amortissements</h2>
    <p>La valeur, la durée et la mise en service sont documentées et figées. Le terrain ne peut jamais produire de dotation.</p>
    {error && <p role="alert" className="ledger-error">{error}</p>}{message && <p role="status">{message}</p>}
    {!setup?.activity ? <p>Initialisez d’abord l’activité, l’exercice et le bien.</p> : <>
      <button disabled={!properties.length} onClick={() => openAsset(false)}>Nouvelle immobilisation</button>
      <button disabled={!properties.length} onClick={() => openAsset(true)}>Inscrire un terrain</button>
      {editor && <ReviewForm key={JSON.stringify(editor)} title={editor.title} fields={editor.fields} onSave={save} onCancel={() => setEditor(null)} retryId={editor.retry} />}
      {assets.map((row) => <article className="entry-card" key={row.id}><h3>{row.label}</h3>
        <p>{row.category} · Valeur {row.acquisition_value} € · Base {row.depreciable_value} € · Non amortissable {row.non_depreciable_value} €</p>
        <p>{row.category === "LAND" ? "Terrain protégé : aucun plan d’amortissement" : `Linéaire sur ${row.useful_life_months} mois · ${row.asset_account} / ${row.depreciation_account}`}</p>
        {row.category === "BUILDING" && <><p>Ajoutez tous les composants avant le premier calcul ; leur total doit couvrir exactement la base.</p><button onClick={() => openComponent(row)}>Ajouter un composant</button></>}
        {row.components.map((part) => <p key={part.id}>↳ {part.label} · {part.value} € · {part.useful_life_months} mois</p>)}
      </article>)}
      <div className="section-heading"><div><h3>Dotations comptables</h3><p>Le calcul en jours calendaires ne modifie jamais la couche fiscale.</p></div>
        <label>Exercice<select value={yearId} onChange={(event) => setYearId(Number(event.target.value))}>{setup.years.filter((year) => year.status === "OPEN").map((year) => <option key={year.id} value={year.id}>{year.year}</option>)}</select></label>
      </div>
      <button disabled={!yearId} onClick={() => { void calculate(); }}>Calculer les périodes</button>
      <div className="ledger-table"><table><thead><tr><th>Actif / composant</th><th>Période</th><th>Jours</th><th>Dotation</th><th>Cumul</th><th>VNC de la base</th><th>État</th></tr></thead><tbody>
        {periods.map((row) => <tr key={row.id}><td>{row.target_label}</td><td>{row.period_start} → {row.period_end}</td><td>{row.days}</td><td>{row.amount} €</td><td>{row.accumulated} €</td><td>{row.net_book_value} €</td><td>{row.status === "POSTED" ? "Comptabilisée" : <button onClick={() => setEditor({ title: `Comptabiliser ${row.target_label}`, path: `/periods/${row.id}/post`, retry: true, fields: [{ name: "piece_reference", label: "Référence de la pièce d’inventaire" }] })}>Comptabiliser</button>}</td></tr>)}
      </tbody></table></div>
    </>}
  </section>;
}
