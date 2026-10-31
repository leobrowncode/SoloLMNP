import { useState } from "react";
import type { Component } from "../api/assets";
import { useUnsavedGuard } from "../routing/useUnsavedGuard";

const MIN = 5;

export default function ComponentJustification({
  part,
  sharedBasis,
  sharedDuration,
  busy,
  onSave,
}: {
  part: Component;
  sharedBasis: boolean;
  sharedDuration: boolean;
  busy: boolean;
  onSave: (data: { basis_reason?: string; duration_reason?: string; reason: string }) => Promise<void>;
}) {
  const savedBasis = sharedBasis ? "" : (part.basis_reason ?? "");
  const savedDuration = sharedDuration ? "" : (part.duration_reason ?? "");
  const [basis, setBasis] = useState(savedBasis);
  const [duration, setDuration] = useState(savedDuration);
  const [showDuration, setShowDuration] = useState(!sharedDuration);
  const [motif, setMotif] = useState("");
  const [review, setReview] = useState(false);
  const [error, setError] = useState("");

  const basisDirty = basis.trim() !== savedBasis.trim();
  const durationDirty = showDuration && duration.trim() !== savedDuration.trim();
  const dirty = basisDirty || durationDirty;
  useUnsavedGuard(dirty || review);

  function verify(): boolean {
    setError("");
    if (!dirty) {
      setError("Saisissez une justification propre à ce composant.");
      return false;
    }
    if (basisDirty && basis.trim().length < MIN) {
      setError("La justification compte au moins 5 caractères.");
      return false;
    }
    if (durationDirty && duration.trim().length < MIN) {
      setError("La justification de la durée compte au moins 5 caractères.");
      return false;
    }
    if (motif.trim().length < MIN) {
      setError("Le motif compte au moins 5 caractères.");
      return false;
    }
    return true;
  }

  async function confirm() {
    const data: { basis_reason?: string; duration_reason?: string; reason: string } = {
      reason: motif.trim(),
    };
    if (basisDirty) data.basis_reason = basis.trim();
    if (durationDirty) data.duration_reason = duration.trim();
    try {
      await onSave(data);
    } catch (reason) {
      setReview(false);
      setError(reason instanceof Error ? reason.message : "Enregistrement impossible.");
    }
  }

  return (
    <span className="row-justification">
      <input
        aria-label={`Justification de ${part.label}`}
        value={basis}
        disabled={busy || review}
        placeholder={sharedBasis ? "Précision propre" : undefined}
        onChange={(event) => {
          setBasis(event.target.value);
          setReview(false);
        }}
      />
      {showDuration ? (
        <input
          aria-label={`Justification de la durée de ${part.label}`}
          value={duration}
          disabled={busy || review}
          placeholder={sharedDuration ? "Durée propre" : undefined}
          onChange={(event) => {
            setDuration(event.target.value);
            setReview(false);
          }}
        />
      ) : (
        <button
          type="button"
          disabled={busy}
          aria-label={`Note de durée de ${part.label}`}
          onClick={() => setShowDuration(true)}
        >
          Note de durée
        </button>
      )}
      {dirty && !review && (
        <label>
          Motif pour {part.label}
          <input
            value={motif}
            disabled={busy}
            onChange={(event) => setMotif(event.target.value)}
          />
        </label>
      )}
      {error && <span role="alert" className="field-error">{error}</span>}
      {review && (
        <span className="field-hint">
          {basisDirty ? basis.trim() : ""}
          {durationDirty ? ` Durée : ${duration.trim()}.` : ""}
          {` Motif : ${motif.trim()}.`}
        </span>
      )}
      {dirty && (
        review ? (
          <button type="button" disabled={busy} onClick={() => { void confirm(); }}>
            {`Confirmer la justification de ${part.label}`}
          </button>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              if (verify()) setReview(true);
            }}
          >
            {`Vérifier la justification de ${part.label}`}
          </button>
        )
      )}
    </span>
  );
}
