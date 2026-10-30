import { useRef, useState } from "react";
import { RequestError, request } from "../api/ledger";
import ApiErrorAlert from "./ApiErrorAlert";
import { toApiError } from "./screenState";

const TYPES: Record<string, string> = {
  "application/pdf": "application/pdf",
  "image/jpeg": "image/jpeg",
  "image/png": "image/png",
};

export default function ConservationPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [entryId, setEntryId] = useState("");
  const [archive, setArchive] = useState("");
  const [receipt, setReceipt] = useState("");
  const [error, setError] = useState("");
  const [apiError, setApiError] = useState<RequestError | null>(null);
  const retryAction = useRef<(() => Promise<void>) | null>(null);

  function clearFeedback() {
    setError("");
    setApiError(null);
    setReceipt("");
  }

  async function upload() {
    clearFeedback();
    const file = fileRef.current?.files?.[0];
    if (!file || !TYPES[file.type]) {
      setError("Choisissez un PDF, un JPEG ou un PNG.");
      return;
    }
    const content = await file.arrayBuffer();
    const bytes = new Uint8Array(content);
    let binary = "";
    bytes.forEach((value) => { binary += String.fromCharCode(value); });
    try {
      const saved = await request<{ sha256: string; original_name: string }>(
        "/documents",
        "POST",
        {
          filename: file.name,
          media_type: TYPES[file.type],
          content_base64: btoa(binary),
          ...(entryId ? { entry_id: Number(entryId) } : {}),
        },
        "/api/filing",
      );
      setReceipt(`Justificatif ${saved.original_name} enregistré. Empreinte ${saved.sha256}.`);
    } catch (reason) {
      retryAction.current = upload;
      setApiError(reason instanceof RequestError ? reason : new RequestError(toApiError(reason), 0));
    }
  }

  async function backup() {
    clearFeedback();
    try {
      const saved = await request<{ filename: string; sha256: string }>("/backup", "POST", {}, "/api/filing");
      setArchive(saved.filename);
      setReceipt(`Sauvegarde ${saved.filename}. Empreinte ${saved.sha256}.`);
    } catch (reason) {
      retryAction.current = backup;
      setApiError(reason instanceof RequestError ? reason : new RequestError(toApiError(reason), 0));
    }
  }

  async function restore() {
    clearFeedback();
    if (!archive) {
      setError("Créez d’abord une sauvegarde, ou indiquez son nom.");
      return;
    }
    try {
      const saved = await request<{ restored_to: string }>("/backup/restore", "POST", { filename: archive }, "/api/filing");
      setReceipt(`Copie contrôlée écrite dans ${saved.restored_to}. La base en service n’est pas remplacée.`);
    } catch (reason) {
      retryAction.current = restore;
      setApiError(reason instanceof RequestError ? reason : new RequestError(toApiError(reason), 0));
    }
  }

  return <section className="ledger-page" aria-labelledby="conservation-title" data-screen-phase="idle">
    <h2 id="conservation-title">Justificatifs et sauvegarde</h2>
    <p>Déposez un PDF ou une photo. Une sauvegarde se crée ici. La restauration prépare une copie de contrôle : elle ne remplace pas les données en cours.</p>
    {error && <p role="alert">{error}</p>}
    {apiError && (
      <ApiErrorAlert
        detail={apiError.detail}
        onRetry={() => { void retryAction.current?.(); }}
      />
    )}
    {receipt && <p role="status">{receipt}</p>}
    <form onSubmit={(event) => { event.preventDefault(); void upload(); }}>
      <label>Justificatif PDF, JPEG ou PNG<input ref={fileRef} type="file" accept="application/pdf,image/jpeg,image/png" /></label>
      <label>Écriture liée, facultative<input inputMode="numeric" value={entryId} onChange={(event) => setEntryId(event.target.value)} /></label>
      <button type="submit">Déposer le justificatif</button>
    </form>
    <div className="toolbar">
      <button type="button" onClick={() => { void backup(); }}>Créer une sauvegarde</button>
      <label>Archive<input value={archive} onChange={(event) => setArchive(event.target.value)} /></label>
      <button type="button" onClick={() => { void restore(); }}>Restaurer vers la copie de contrôle</button>
    </div>
  </section>;
}
