import { useState } from "react";
import { amount, cents } from "../api/ledger";
export interface Field {
  name: string; label: string; type?: "date" | "text" | "number"; money?: boolean;
  value?: string | undefined; choices?: [string, string][]; optional?: boolean;
}
export default function ReviewForm({ title, fields, onSave, onCancel, retryId = false }: {
  title: string; fields: Field[]; onSave: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void; retryId?: boolean | undefined;
}) {
  const [review, setReview] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return <form className="entry-editor" onSubmit={(event) => {
    event.preventDefault(); setError("");
    if (!review) {
      try {
        const form = new FormData(event.currentTarget);
        const data: Record<string, unknown> = {};
        for (const field of fields) {
          const value = String(form.get(field.name) ?? "");
          data[field.name] = field.money ? amount(cents(value))
            : field.type === "number" ? (value ? Number(value) : null)
            : value || (field.optional ? null : "");
        }
        if (retryId) data.request_id = crypto.randomUUID();
        setReview(data);
      } catch (e) { setError(e instanceof Error ? e.message : "Champs invalides."); }
    } else {
      setBusy(true);
      void onSave(review).catch((e: Error) => setError(e.message)).finally(() => setBusy(false));
    }
  }}>
    <h3>{title}</h3>
    {error && <p role="alert">{error}</p>}
    <div hidden={review !== null}>{fields.map((field) => <label key={field.name}>{field.label}
      {field.choices ? <select name={field.name} defaultValue={field.value} required={!field.optional}>
        {field.choices.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select> : <input name={field.name} defaultValue={field.value ?? (field.money ? "0.00" : "")}
        type={field.type === "number" ? "number" : field.type ?? "text"} min={field.type === "number" ? "1" : undefined}
        inputMode={field.money ? "decimal" : undefined} required={!field.optional} />}
    </label>)}</div>
    {review && <>
      <p>Vérifiez les informations avant de confirmer. Les opérations comptabilisées seront définitives et pourront être corrigées par extourne.</p>
      <dl>{fields.map((field) => <div key={field.name}><dt>{field.label}</dt><dd>{field.choices?.find(([value]) => value === String(review[field.name] ?? ""))?.[1] ?? String(review[field.name] ?? "—")}</dd></div>)}</dl>
      <button type="button" disabled={busy} onClick={() => setReview(null)}>Corriger la saisie</button>
    </>}
    <button disabled={busy}>{busy ? "Enregistrement…" : review ? "Confirmer l’enregistrement" : "Vérifier avant enregistrement"}</button>
    <button type="button" disabled={busy} onClick={onCancel}>Annuler</button>
  </form>;
}
