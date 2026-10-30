import { useEffect, useRef, useState } from "react";
import {
  entryLabel, frStamp, integrityLabel, octets,
  type BackupRow, type EntryChoice, type RestorePreview, type SupportingDocumentRow,
} from "../api/conservation";
import { RequestError, request } from "../api/ledger";
import ApiErrorAlert from "./ApiErrorAlert";
import { describedBy, linkCauses, restoreCauses } from "./actionCauses";
import EntryPicker from "./EntryPicker";
import GlossaryTip from "./GlossaryTip";
import PrerequisiteList from "./PrerequisiteList";
import ScreenStatus from "./ScreenStatus";
import MutationStatus from "./MutationStatus";
import { useMutation } from "./useMutation";
import {
  beginLoad, defer, failLoad, finishLoad, idleView, showsData, toApiError, type ScreenView,
} from "./screenState";
import FrenchFileInput from "../lib/FrenchFileInput";
import FrenchForm from "../lib/FrenchForm";

const TYPES: Record<string, string> = {
  "application/pdf": "application/pdf",
  "image/jpeg": "image/jpeg",
  "image/png": "image/png",
};

function pagePhase(documents: ScreenView<unknown>, backups: ScreenView<unknown>): ScreenView<unknown>["phase"] {
  if (documents.phase === "loading" || backups.phase === "loading") return "loading";
  if (documents.phase === "error" || backups.phase === "error") return "error";
  if (documents.phase === "idle" || backups.phase === "idle") return "idle";
  return "loaded";
}

export default function ConservationPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [documentsView, setDocumentsView] = useState<ScreenView<SupportingDocumentRow[]>>(
    () => beginLoad(idleView<SupportingDocumentRow[]>(), false),
  );
  const [backupsView, setBackupsView] = useState<ScreenView<BackupRow[]>>(
    () => beginLoad(idleView<BackupRow[]>(), false),
  );
  const [attempt, setAttempt] = useState(0);
  const [choice, setChoice] = useState<EntryChoice | null>(null);
  const [selectedBackup, setSelectedBackup] = useState("");
  const [preview, setPreview] = useState<ScreenView<RestorePreview>>(idleView());
  const [previewAttempt, setPreviewAttempt] = useState(0);
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [apiError, setApiError] = useState<RequestError | null>(null);
  const [receipt, setReceipt] = useState("");
  const { busy, step, run } = useMutation();
  const retryAction = useRef<(() => Promise<void>) | null>(null);
  const documents = showsData(documentsView) ? documentsView.data : null;
  const backups = showsData(backupsView) ? backupsView.data : null;
  const previewReady = preview.phase === "loaded" && preview.data?.filename === selectedBackup;
  const restoreBlocked = restoreCauses(Boolean(selectedBackup), previewReady, confirmation);
  const linkBlocked = linkCauses(choice !== null);

  function clearFeedback() {
    setError("");
    setApiError(null);
    setReceipt("");
  }

  function reload() {
    setAttempt((value) => value + 1);
  }

  useEffect(() => {
    let current = true;
    defer(() => {
      if (!current) return;
      setDocumentsView((previous) => beginLoad(previous, previous.data !== null));
      setBackupsView((previous) => beginLoad(previous, previous.data !== null));
    });
    void request<{ documents: SupportingDocumentRow[] }>("/documents", "GET", undefined, "/api/filing").then(
      (value) => {
        if (current) setDocumentsView(finishLoad(value.documents, (rows) => rows.length === 0));
      },
      (reason: unknown) => {
        if (current) {
          setDocumentsView((previous) => failLoad(previous, toApiError(reason), previous.data !== null));
        }
      },
    );
    void request<{ backups: BackupRow[] }>("/backups", "GET", undefined, "/api/filing").then(
      (value) => {
        if (current) setBackupsView(finishLoad(value.backups, (rows) => rows.length === 0));
      },
      (reason: unknown) => {
        if (current) {
          setBackupsView((previous) => failLoad(previous, toApiError(reason), previous.data !== null));
        }
      },
    );
    return () => { current = false; };
  }, [attempt]);

  useEffect(() => {
    let current = true;
    if (!selectedBackup) {
      defer(() => {
        if (current) setPreview(idleView());
      });
      return () => { current = false; };
    }
    defer(() => {
      if (current) setPreview((previous) => beginLoad(previous, false));
    });
    const filename = selectedBackup;
    void request<RestorePreview>(
      `/backups/preview?filename=${encodeURIComponent(filename)}`,
      "GET",
      undefined,
      "/api/filing",
    ).then((value) => {
      if (current) setPreview(finishLoad(value));
    }, (reason: unknown) => {
      if (current) setPreview(failLoad(idleView<RestorePreview>(), toApiError(reason), false));
    });
    return () => { current = false; };
  }, [selectedBackup, previewAttempt]);

  async function upload() {
    await run(async (report) => {
      clearFeedback();
      const file = fileRef.current?.files?.[0];
      if (!file || !TYPES[file.type]) {
        setError("Choisissez un PDF, un JPEG ou un PNG.");
        return;
      }
      report("Dépôt du justificatif…");
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
            ...(choice ? {
              entry_number: choice.entry_number,
              accounting_date: choice.accounting_date,
              piece_reference: choice.piece_reference,
            } : {}),
          },
          "/api/filing",
        );
        setReceipt(`Justificatif ${saved.original_name} enregistré. Empreinte ${saved.sha256}.`);
        reload();
      } catch (reason) {
        retryAction.current = upload;
        setApiError(reason instanceof RequestError ? reason : new RequestError(toApiError(reason), 0));
      }
    });
  }

  async function link(documentId: number) {
    if (!choice) return;
    const selected = choice;
    await run(async (report) => {
      clearFeedback();
      report("Liaison du justificatif…");
      try {
        const saved = await request<SupportingDocumentRow>(
          `/documents/${documentId}/link`,
          "POST",
          {
            entry_number: selected.entry_number,
            accounting_date: selected.accounting_date,
            piece_reference: selected.piece_reference,
          },
          "/api/filing",
        );
        setReceipt(`Justificatif ${saved.original_name} lié à ${entryLabel(saved.entry)}.`);
        reload();
      } catch (reason) {
        retryAction.current = () => link(documentId);
        setApiError(reason instanceof RequestError ? reason : new RequestError(toApiError(reason), 0));
      }
    });
  }

  async function backup() {
    await run(async (report) => {
      clearFeedback();
      report("Création de la sauvegarde…");
      try {
        const saved = await request<{ filename: string; sha256: string }>("/backup", "POST", {}, "/api/filing");
        setReceipt(`Sauvegarde ${saved.filename}. Empreinte ${saved.sha256}.`);
        setSelectedBackup(saved.filename);
        reload();
      } catch (reason) {
        retryAction.current = backup;
        setApiError(reason instanceof RequestError ? reason : new RequestError(toApiError(reason), 0));
      }
    });
  }

  async function verify(filename: string) {
    await run(async (report) => {
      clearFeedback();
      report("Contrôle de la sauvegarde…");
      try {
        const saved = await request<BackupRow>("/backups/verify", "POST", { filename }, "/api/filing");
        setReceipt(`Contrôle de ${saved.filename} : ${integrityLabel(saved.integrity)}`);
        reload();
      } catch (reason) {
        retryAction.current = () => verify(filename);
        setApiError(reason instanceof RequestError ? reason : new RequestError(toApiError(reason), 0));
        reload();
      }
    });
  }

  async function restore() {
    if (restoreBlocked.length > 0 || !selectedBackup) return;
    const filename = selectedBackup;
    await run(async (report) => {
      clearFeedback();
      report("Restauration de la sauvegarde…");
      try {
        const saved = await request<{
          restored_from: string;
          pre_restore_backup: string;
          entries: number;
          years: number;
        }>(
          "/backup/restore",
          "POST",
          { filename, confirmation: "RESTAURER" },
          "/api/filing",
        );
        setReceipt(
          `Base restaurée depuis ${saved.restored_from} (${saved.entries} écritures, ${saved.years} exercices). `
          + `Copie préalable : ${saved.pre_restore_backup}.`,
        );
        setConfirmation("");
        setSelectedBackup("");
        reload();
      } catch (reason) {
        retryAction.current = restore;
        setApiError(reason instanceof RequestError ? reason : new RequestError(toApiError(reason), 0));
      }
    });
  }

  const shownPreview = showsData(preview) ? preview.data : null;

  return (
    <section
      className="ledger-page"
      aria-labelledby="conservation-title"
      data-screen-phase={pagePhase(documentsView, backupsView)}
    >
      <div className="heading-with-help">
        <h2 id="conservation-title">Justificatifs et sauvegarde</h2>
        <GlossaryTip id="justificatif" />
        <GlossaryTip id="sauvegarde" />
        <GlossaryTip id="restauration" />
        <GlossaryTip id="empreinte" />
      </div>
      <p>
        Déposez un PDF ou une photo, puis reliez-le à une écriture par son numéro, sa date et sa pièce.
        Une sauvegarde se choisit dans la liste. La restauration montre ce qui change, exige la confirmation
        RESTAURER, et enregistre d’abord une copie de l’état actuel. Une écriture validée ne se modifie pas :
        seule la base entière est reprise.
      </p>
      <MutationStatus step={step} />
      {error && <p role="alert">{error}</p>}
      {apiError && (
        <ApiErrorAlert
          detail={apiError.detail}
          onRetry={() => { void retryAction.current?.(); }}
        />
      )}
      {receipt && <p role="status">{receipt}</p>}

      <h3 id="justificatifs">Justificatifs</h3>
      <ScreenStatus
        state={documentsView}
        onRetry={reload}
        loading={<p role="status">Chargement des justificatifs…</p>}
        empty={<p>Aucun justificatif déposé.</p>}
      />
      {documents && documents.length > 0 && (
        <div className="ledger-table">
          <table>
            <caption>Inventaire des justificatifs</caption>
            <thead>
              <tr>
                <th>Nom</th>
                <th>Date</th>
                <th>Type</th>
                <th>Taille</th>
                <th>Empreinte SHA-256</th>
                <th>Écriture liée</th>
                <th>Liaison</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => (
                <tr key={document.id}>
                  <td>{document.original_name}</td>
                  <td>{frStamp(document.created_at)}</td>
                  <td>{document.media_label}</td>
                  <td>{octets(document.size)}</td>
                  <td className="fingerprint">{document.sha256}</td>
                  <td>{entryLabel(document.entry)}</td>
                  <td>
                    <button
                      type="button"
                      disabled={busy || linkBlocked.length > 0}
                      aria-busy={busy || undefined}
                      aria-describedby={describedBy("link-causes", linkBlocked)}
                      onClick={() => { void link(document.id); }}
                    >
                      {document.entry ? "Changer la liaison" : "Lier cette écriture"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {documents && documents.length > 0 && (
        <PrerequisiteList id="link-causes" causes={linkBlocked} />
      )}
      <EntryPicker selected={choice} onSelect={setChoice} />
      <FrenchForm onSubmit={(event) => { event.preventDefault(); void upload(); }}>
        <FrenchFileInput
          label="Justificatif PDF, JPEG ou PNG"
          accept="application/pdf,image/jpeg,image/png"
          inputRef={fileRef}
          disabled={busy}
        />
        <button type="submit" disabled={busy} aria-busy={busy || undefined}>Déposer le justificatif</button>
      </FrenchForm>

      <h3 id="sauvegardes">Sauvegardes</h3>
      <div className="toolbar">
        <button type="button" disabled={busy} aria-busy={busy || undefined} onClick={() => { void backup(); }}>Créer une sauvegarde</button>
      </div>
      <ScreenStatus
        state={backupsView}
        onRetry={reload}
        loading={<p role="status">Chargement des sauvegardes…</p>}
        empty={<p>Aucune sauvegarde enregistrée.</p>}
      />
      {backups && backups.length > 0 && (
        <div className="ledger-table">
          <table>
            <caption>Inventaire des sauvegardes</caption>
            <thead>
              <tr>
                <th>Choisir</th>
                <th>Date</th>
                <th>Taille</th>
                <th>Version</th>
                <th>Empreinte SHA-256</th>
                <th>Dernier contrôle</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {backups.map((archive) => {
                const when = frStamp(archive.created_at);
                return (
                  <tr key={archive.filename}>
                    <td>
                      <label>
                        <input
                          type="radio"
                          name="backup-choice"
                          checked={selectedBackup === archive.filename}
                          onChange={() => setSelectedBackup(archive.filename)}
                        />
                        Choisir la sauvegarde du {when}
                      </label>
                    </td>
                    <td>{when}</td>
                    <td>{octets(archive.size)}</td>
                    <td>
                      {archive.application_version ?? "—"}
                      {" · schéma "}
                      {archive.schema_revision ?? "—"}
                    </td>
                    <td className="fingerprint">{archive.sha256}</td>
                    <td>{integrityLabel(archive.integrity)}</td>
                    <td>
                      <button
                        type="button"
                        disabled={busy}
                        aria-busy={busy || undefined}
                        onClick={() => { void verify(archive.filename); }}
                      >
                        Contrôler la sauvegarde du {when}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div id="restore-preview">
        <h3>Restauration</h3>
        <ScreenStatus
          state={preview}
          onRetry={() => setPreviewAttempt((value) => value + 1)}
          loading={<p role="status">Chargement de l’aperçu…</p>}
        />
        {shownPreview && (
          <dl className="review-list">
            <div>
              <dt>Date de la sauvegarde</dt>
              <dd>{frStamp(shownPreview.backup_date)}</dd>
            </div>
            <div>
              <dt>Écritures</dt>
              <dd>{shownPreview.current.entries} → {shownPreview.backup.entries}</dd>
            </div>
            <div>
              <dt>Exercices</dt>
              <dd>{shownPreview.current.years} → {shownPreview.backup.years}</dd>
            </div>
          </dl>
        )}
        <label id="restore-confirmation">
          Confirmation — saisir RESTAURER
          <input
            value={confirmation}
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => setConfirmation(event.target.value)}
            placeholder="RESTAURER"
          />
        </label>
        <button
          type="button"
          disabled={busy || restoreBlocked.length > 0}
          aria-busy={busy || undefined}
          aria-describedby={describedBy("restore-causes", restoreBlocked)}
          onClick={() => { void restore(); }}
        >
          {busy ? "Restauration…" : "Restaurer la sauvegarde"}
        </button>
        <PrerequisiteList id="restore-causes" causes={restoreBlocked} />
      </div>
    </section>
  );
}
