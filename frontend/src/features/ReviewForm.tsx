import { useId, useMemo, useRef, useState } from "react";
import { amount, cents } from "../api/ledger";

export interface Field {
  name: string;
  label: string;
  type?: "date" | "text" | "number";
  money?: boolean;
  value?: string | undefined;
  choices?: [string, string][];
  /** Options that depend on the current draft (category, asset account, …). */
  choicesFor?: ((draft: Record<string, string>) => [string, string][]) | undefined;
  optional?: boolean;
  /** UI-only field excluded from the save payload (backend forbids extras). */
  local?: boolean;
  group?: string;
  hint?: string;
}

function readField(field: Field, raw: string): unknown {
  if (field.money) return amount(cents(raw));
  if (field.type === "number") return raw ? Number(raw) : null;
  return raw || (field.optional ? null : "");
}

function choicesOf(field: Field, draft: Record<string, string>): [string, string][] | undefined {
  return field.choicesFor?.(draft) ?? field.choices;
}

function labelOf(field: Field, value: unknown, draft: Record<string, string>): string {
  const key = String(value ?? "");
  return choicesOf(field, draft)?.find(([choice]) => choice === key)?.[1] ?? (key || "—");
}

export default function ReviewForm({
  title,
  fields,
  onSave,
  onCancel,
  retryId = false,
  help,
  sumInto,
  derive,
}: {
  title: string;
  fields: Field[];
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
  retryId?: boolean | undefined;
  help?: string | undefined;
  /** Compute this money field from the sum of other money fields before save. */
  sumInto?: { target: string; sources: string[] } | undefined;
  /** Derive dependent fields after a user change. piece_reference is only applied if empty or still auto. */
  derive?: ((draft: Record<string, string>, changed: string) => Partial<Record<string, string>>) | undefined;
}) {
  const [review, setReview] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((field) => [
      field.name,
      field.value ?? field.choices?.[0]?.[0] ?? (field.money ? "0.00" : ""),
    ])),
  );
  const formUid = useId();
  const autoRef = useRef(
    derive?.({
      ...Object.fromEntries(fields.map((field) => [
        field.name,
        field.value ?? field.choices?.[0]?.[0] ?? (field.money ? "0.00" : ""),
      ])),
    }, "")?.piece_reference
      ?? fields.find((field) => field.name === "piece_reference")?.value
      ?? "",
  );

  const groups = useMemo(() => {
    const order: string[] = [];
    const map = new Map<string, Field[]>();
    for (const field of fields) {
      const key = field.group ?? "";
      if (!map.has(key)) {
        map.set(key, []);
        order.push(key);
      }
      map.get(key)!.push(field);
    }
    return order.map((key) => ({ key, fields: map.get(key)! }));
  }, [fields]);

  const liveTotal = useMemo(() => {
    if (!sumInto) return null;
    try {
      const total = sumInto.sources.reduce((sum, name) => sum + cents(draft[name] ?? "0.00"), 0n);
      return amount(total);
    } catch {
      return null;
    }
  }, [draft, sumInto]);

  function applyChange(name: string, value: string) {
    setDraft((current) => {
      const next = { ...current, [name]: value };
      if (!derive) return next;
      const patch = derive(next, name);
      const result = { ...next };
      for (const [key, patchValue] of Object.entries(patch)) {
        if (patchValue === undefined) continue;
        if (key === "piece_reference") {
          const currentRef = current.piece_reference ?? "";
          if (name === "piece_reference") {
            // Manual edit of the reference itself — keep the typed value.
            continue;
          }
          if (currentRef === "" || currentRef === autoRef.current) {
            result.piece_reference = patchValue;
            autoRef.current = patchValue;
          }
        } else if (key !== name) {
          result[key] = patchValue;
        }
      }
      return result;
    });
  }

  function buildPayload(values: Record<string, string>): Record<string, unknown> {
    const data: Record<string, unknown> = {};
    for (const field of fields) {
      if (field.local) continue;
      data[field.name] = readField(field, values[field.name] ?? "");
    }
    if (sumInto) {
      const total = sumInto.sources.reduce((sum, name) => sum + cents(String(data[name] ?? "0.00")), 0n);
      if (total <= 0n) throw new Error("Saisissez au moins un montant de ventilation supérieur à zéro.");
      data[sumInto.target] = amount(total);
    }
    if (retryId) data.request_id = crypto.randomUUID();
    return data;
  }

  return (
    <form
      className="entry-editor review-form"
      onSubmit={(event) => {
        event.preventDefault();
        setError("");
        if (!review) {
          try {
            setReview(buildPayload(draft));
          } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Champs invalides.");
          }
          return;
        }
        setBusy(true);
        void onSave(review)
          .catch((reason: Error) => setError(reason.message))
          .finally(() => setBusy(false));
      }}
    >
      <h3>{title}</h3>
      {help && <p className="form-help">{help}</p>}
      {error && <p role="alert" className="ledger-error">{error}</p>}

      {!review && groups.map(({ key, fields: groupFields }) => (
        <fieldset key={key || "main"} className="form-fieldset">
          {key ? <legend>{key}</legend> : null}
          <div className="form-grid">
            {groupFields.map((field) => {
              const controlId = `${formUid}-${field.name}`;
              const hintId = field.hint ? `${controlId}-hint` : undefined;
              const choices = choicesOf(field, draft);
              return (
                <div key={field.name} className={field.money ? "form-field field-money" : "form-field"}>
                  <label htmlFor={controlId}>
                    {field.label}{field.optional ? " (facultatif)" : ""}
                  </label>
                  {choices ? (
                    <select
                      id={controlId}
                      name={field.name}
                      aria-describedby={hintId}
                      value={draft[field.name] ?? ""}
                      required={!field.optional}
                      onChange={(event) => applyChange(field.name, event.target.value)}
                    >
                      {field.optional && (
                        <option value="">
                          {choices.find(([value]) => value === "")?.[1] ?? "—"}
                        </option>
                      )}
                      {choices.filter(([value]) => value !== "").map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      id={controlId}
                      name={field.name}
                      aria-describedby={hintId}
                      value={draft[field.name] ?? ""}
                      type={field.type === "number" ? "number" : field.type ?? "text"}
                      min={field.type === "number" ? "1" : undefined}
                      step={field.money ? "0.01" : undefined}
                      inputMode={field.money ? "decimal" : undefined}
                      required={!field.optional}
                      onChange={(event) => applyChange(field.name, event.target.value)}
                    />
                  )}
                  <span id={hintId} className="field-hint">{field.hint ?? ""}</span>
                </div>
              );
            })}
          </div>
          {sumInto && key && groupFields.some((field) => sumInto.sources.includes(field.name)) && (
            <p className="form-total" aria-live="polite">
              Total de l’échéance : <strong>{liveTotal ?? "—"} €</strong>
            </p>
          )}
        </fieldset>
      ))}

      {review && (
        <div className="review-summary">
          <p>Vérifiez les informations avant de confirmer. Les opérations comptabilisées seront définitives et pourront être corrigées par extourne.</p>
          <dl className="review-list">
            {fields.filter((field) => !field.local).map((field) => (
              <div key={field.name}>
                <dt>{field.label}</dt>
                <dd>{labelOf(field, review[field.name], draft)}</dd>
              </div>
            ))}
            {sumInto && (
              <div>
                <dt>Montant total débitée / créditée</dt>
                <dd>{String(review[sumInto.target])} €</dd>
              </div>
            )}
          </dl>
          <button type="button" disabled={busy} onClick={() => setReview(null)}>Corriger la saisie</button>
        </div>
      )}

      <div className="form-actions">
        <button disabled={busy} type="submit">
          {busy ? "Enregistrement…" : review ? "Confirmer l’enregistrement" : "Vérifier avant enregistrement"}
        </button>
        <button type="button" disabled={busy} onClick={onCancel}>Annuler</button>
      </div>
    </form>
  );
}
