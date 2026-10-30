import { useEffect, useRef, useState } from "react";
import { downloadFiling } from "../api/download";
import { RequestError } from "../api/ledger";
import ApiErrorAlert from "./ApiErrorAlert";
import PrerequisiteList from "./PrerequisiteList";
import type { ExportSlot, ExportStatus } from "./exportStatus";
import GlossaryTip from "./GlossaryTip";
import MutationStatus from "./MutationStatus";
import { useMutation } from "./useMutation";

const OUTPUTS: {
  kind: "liasse" | "pdf" | "fec" | "archive";
  title: string;
  family: "liasse" | "fec";
  action?: string;
  path?: (yearId: number) => string;
}[] = [
  {
    kind: "liasse",
    title: "Liasse",
    family: "liasse",
  },
  {
    kind: "pdf",
    title: "PDF de recopie",
    family: "liasse",
    action: "Télécharger le PDF de recopie",
    path: (yearId) => `/api/filing/years/${yearId}/efi.pdf`,
  },
  {
    kind: "fec",
    title: "FEC",
    family: "fec",
    action: "Télécharger le FEC",
    path: (yearId) => `/api/filing/years/${yearId}/fec`,
  },
  {
    kind: "archive",
    title: "Dossier de contrôle",
    family: "fec",
    action: "Télécharger le dossier de contrôle",
    path: (yearId) => `/api/filing/years/${yearId}/archive`,
  },
];

const BLOCKED: ExportSlot = { posture: "bloquee", label: "Bloquée", download: false };

function slotOf(status: ExportStatus, kind: "liasse" | "pdf" | "fec" | "archive"): ExportSlot {
  const slot = status.exports[kind];
  if (
    slot
    && (slot.posture === "provisoire" || slot.posture === "bloquee" || slot.posture === "finale")
    && typeof slot.download === "boolean"
  ) {
    return slot;
  }
  return BLOCKED;
}

export default function ExportDownloads({ yearId, status }: { yearId: number; status: ExportStatus }) {
  const [error, setError] = useState<RequestError | null>(null);
  const { busy, step, run } = useMutation();
  const errorRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    errorRef.current?.querySelector<HTMLElement>("[role=alert]")?.focus();
  }, [error]);

  async function download(path: string) {
    await run(async (report) => {
      report("Téléchargement…");
      setError(null);
      try {
        await downloadFiling(path);
      } catch (reason) {
        setError(reason instanceof RequestError
          ? reason
          : new RequestError(
            { code: "HTTP_ERROR", message: "Le téléchargement a échoué. Réessayez depuis cette page." },
            0,
          ));
      }
    });
  }

  return (
    <div className="export-board">
      <MutationStatus step={step} />
      <div ref={errorRef}>
        {error && <ApiErrorAlert detail={error.detail} />}
      </div>
      <div className="export-board-list">
        {OUTPUTS.map((output) => {
          const slot = slotOf(status, output.kind);
          const prerequisites = (status.prerequisites ?? []).filter((item) => item.export === output.family);
          const hintId = `export-${output.kind}-hint`;
          return (
            <article
              key={output.kind}
              className={`export-card export-card-${slot.posture}`}
              data-export={output.kind}
              data-posture={slot.posture}
            >
              <header>
                <div className="heading-with-help">
                  <h4>{output.title}</h4>
                  {output.kind === "liasse" && <GlossaryTip id="liasse" />}
                  {output.kind === "pdf" && <GlossaryTip id="efi" />}
                  {output.kind === "fec" && <GlossaryTip id="fec" />}
                  {output.kind === "archive" && <GlossaryTip id="dossier-controle" />}
                </div>
                <p className="export-posture">{slot.label}</p>
              </header>
              <div id={hintId}>
                {slot.posture === "provisoire" && (
                  <p>Document provisoire : ce n’est pas une sortie finale.</p>
                )}
                {slot.posture === "finale" && output.kind !== "liasse" && <p>Sortie finale.</p>}
                {slot.posture === "bloquee" && output.kind === "liasse" && (
                  <PrerequisiteList causes={prerequisites} intro="" />
                )}
                {slot.posture === "bloquee" && output.kind === "pdf" && (
                  <p>Le PDF reste bloqué tant que la liasse l’est. Les prérequis sont indiqués au-dessus.</p>
                )}
                {slot.posture === "bloquee" && output.kind === "fec" && (
                  <PrerequisiteList causes={prerequisites} intro="" />
                )}
                {slot.posture === "bloquee" && output.kind === "archive" && (
                  <p>Le dossier de contrôle suit le FEC. Les prérequis sont indiqués sur la carte FEC.</p>
                )}
                {output.kind === "liasse" && (
                  <p>Le PDF porte la même posture. Les prérequis s’affichent avant le téléchargement.</p>
                )}
              </div>
              {output.action && output.path && (
                <button
                  type="button"
                  disabled={!slot.download || busy}
                  aria-busy={busy || undefined}
                  aria-describedby={hintId}
                  onClick={() => { void download(output.path?.(yearId) ?? ""); }}
                >
                  {output.action}
                </button>
              )}
            </article>
          );
        })}
        <article className="export-card" data-export="tableur">
          <header>
            <h4>Tableur de travail</h4>
          </header>
          <p id="export-tableur-hint">
            Opérations, journal, balance et amortissements. La feuille Liasse reprend la posture affichée ci-dessus.
          </p>
          <button
            type="button"
            disabled={busy}
            aria-busy={busy || undefined}
            aria-describedby="export-tableur-hint"
            onClick={() => { void download(`/api/filing/years/${yearId}/export.xlsx`); }}
          >
            Export tableur (.xlsx, Google Sheets)
          </button>
        </article>
      </div>
    </div>
  );
}
