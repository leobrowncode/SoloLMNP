import { useState } from "react";
import { entryLabel, frStamp, type EntryChoice } from "../api/conservation";
import { RequestError, request } from "../api/ledger";
import ApiErrorAlert from "./ApiErrorAlert";
import GlossaryTip from "./GlossaryTip";
import { toApiError } from "./screenState";

export default function EntryPicker({
  selected,
  onSelect,
}: {
  selected: EntryChoice | null;
  onSelect: (entry: EntryChoice | null) => void;
}) {
  const [number, setNumber] = useState("");
  const [entryDate, setEntryDate] = useState("");
  const [piece, setPiece] = useState("");
  const [results, setResults] = useState<EntryChoice[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<RequestError | null>(null);
  const [busy, setBusy] = useState(false);

  async function search() {
    setError(null);
    setSearched(false);
    const params = new URLSearchParams();
    if (number.trim()) params.set("number", number.trim());
    if (entryDate) params.set("entry_date", entryDate);
    if (piece.trim()) params.set("piece", piece.trim());
    if ([...params.keys()].length === 0) {
      setError(new RequestError({
        code: "ENTRY_SEARCH",
        message: "Indiquez un numéro, une date ou une pièce.",
        help: "ecriture",
      }, 422));
      setResults([]);
      return;
    }
    setBusy(true);
    try {
      const found = await request<{ entries: EntryChoice[] }>(
        `/entries?${params.toString()}`,
        "GET",
        undefined,
        "/api/filing",
      );
      setResults(found.entries);
      setSearched(true);
    } catch (reason) {
      setResults([]);
      setError(reason instanceof RequestError ? reason : new RequestError(toApiError(reason), 0));
    } finally {
      setBusy(false);
    }
  }

  return (
    <fieldset className="form-fieldset" id="entry-picker">
      <legend>
        Écriture à lier
        <GlossaryTip id="ecriture" />
      </legend>
      <p className="form-help">
        Recherchez par numéro, date ou pièce. Le sélecteur ne demande pas d’identifiant interne.
      </p>
      <div className="form-grid">
        <label>
          Numéro d’écriture
          <input value={number} onChange={(event) => setNumber(event.target.value)} autoComplete="off" />
        </label>
        <label>
          Date de l’écriture
          <input type="date" value={entryDate} onChange={(event) => setEntryDate(event.target.value)} />
        </label>
        <label>
          Pièce
          <input value={piece} onChange={(event) => setPiece(event.target.value)} autoComplete="off" />
        </label>
      </div>
      <button type="button" onClick={() => { void search(); }} disabled={busy}>
        {busy ? "Recherche…" : "Rechercher une écriture"}
      </button>
      {error && <ApiErrorAlert detail={error.detail} onRetry={() => { void search(); }} />}
      {searched && results.length === 0 && <p>Aucune écriture ne correspond.</p>}
      {results.length > 0 && (
        <div className="picker-results" role="radiogroup" aria-label="Écritures trouvées">
          {results.map((entry) => {
            const key = `${entry.entry_number ?? "brouillon"}-${entry.accounting_date}-${entry.piece_reference}`;
            const checked = selected !== null
              && selected.entry_number === entry.entry_number
              && selected.accounting_date === entry.accounting_date
              && selected.piece_reference === entry.piece_reference;
            return (
              <label key={key}>
                <input
                  type="radio"
                  name="entry-choice"
                  checked={checked}
                  onChange={() => onSelect(entry)}
                />
                {entryLabel(entry)} — {entry.label} ({frStamp(entry.piece_date)})
              </label>
            );
          })}
        </div>
      )}
    </fieldset>
  );
}
