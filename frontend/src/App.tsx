import { useEffect, useState, type ReactNode } from "react";
import { fetchStatus, type ApplicationStatus } from "./api/status";
import LedgerPage from "./features/LedgerPage";
import OperationsPage from "./features/OperationsPage";
import AssetsPage from "./features/AssetsPage";
import StatementsPage from "./features/StatementsPage";
import FiscalPage from "./features/FiscalPage";
import ConservationPage from "./features/ConservationPage";

type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "loaded"; data: ApplicationStatus };
type PageId = "overview" | "ledger" | "operations" | "assets" | "statements" | "fiscal" | "conservation";

const navItems: { id: PageId; label: string; step?: string; hint: string }[] = [
  { id: "overview", label: "Vue d’ensemble", hint: "Par où commencer." },
  { id: "ledger", label: "Comptabilité", step: "1", hint: "Activité, exercice, puis écritures validées." },
  { id: "operations", label: "Opérations & banque", step: "2", hint: "Bien, banque, emprunt, loyers et charges." },
  { id: "assets", label: "Immobilisations", step: "3", hint: "Terrain, bâtiment, mobilier, puis dotations." },
  { id: "statements", label: "États comptables", step: "4", hint: "Bilan, résultat, puis centralisation." },
  { id: "fiscal", label: "Fiscalité LMNP", step: "5", hint: "Calcul fiscal, pré-contrôle, clôture, puis liasse." },
  { id: "conservation", label: "Conservation", step: "6", hint: "Justificatifs et sauvegarde." },
];

export default function App() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [page, setPage] = useState<PageId>("overview");
  useEffect(() => {
    const controller = new AbortController();
    void fetchStatus(controller.signal).then(
      (data) => { if (!controller.signal.aborted) setState({ kind: "loaded", data }); },
      () => { if (!controller.signal.aborted) setState({ kind: "error" }); },
    );
    return () => controller.abort();
  }, [attempt]);

  const status = state.kind === "loaded" ? state.data : null;
  const ready = status?.database.status === "ready";
  function refresh() {
    setState({ kind: "loading" });
    setAttempt((current) => current + 1);
  }

  let workspace: ReactNode = null;
  if (ready) {
    if (page === "ledger") workspace = <LedgerPage />;
    else if (page === "operations") workspace = <OperationsPage />;
    else if (page === "assets") workspace = <AssetsPage />;
    else if (page === "statements") workspace = <StatementsPage />;
    else if (page === "fiscal") workspace = <FiscalPage />;
    else if (page === "conservation") workspace = <ConservationPage />;
  }

  return (
    <div className="app-layout">
      <a className="skip-link" href="#main">Aller au contenu</a>
      <aside className="sidebar">
        <a href="#main" className="brand" aria-label="SoloLMNP — accueil" onClick={() => setPage("overview")}>
          <span className="brand-mark" aria-hidden="true">S</span>
          <span>Solo<span className="brand-light">LMNP</span></span>
        </a>
        <p className="sidebar-label">PARCOURS DÉCLARATIF</p>
        <nav aria-label="Navigation principale">
          {navItems.map((item) => (
            <a
              key={item.id}
              href="#main"
              className={page === item.id ? "nav-active" : undefined}
              aria-current={page === item.id ? "page" : undefined}
              onClick={() => setPage(item.id)}
            >
              {item.step ? <span className="nav-step" aria-hidden="true">{item.step}</span> : <span aria-hidden="true">◫</span>}
              {item.label}
            </a>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="small-dot" aria-hidden="true" />
          <strong>Dans l’ordre du menu</strong>
          <p>Une étape à la fois. SoloLMNP n’envoie rien aux impôts.</p>
        </div>
        <div className="sidebar-version">SoloLMNP · {status ? `v${status.application_version}` : "Développement"}</div>
      </aside>

      <main id="main" tabIndex={-1}>
        <header className="topbar">
          <p className="topbar-title">{navItems.find((item) => item.id === page)?.label}</p>
          {ready && <p>Base prête. Vous recopiez la liasse vous-même. Aucun envoi n’est effectué.</p>}
        </header>
        <div className="content">
          {status?.storage_warning && (
            <div className="notice notice-error" role="alert">
              <strong>Stockage non sûr</strong>
              <p>{status.storage_warning}</p>
            </div>
          )}
          {workspace}

          {page === "overview" && ready && (
            <section className="intro" aria-labelledby="welcome-title">
              <h1 id="welcome-title">De l’écriture à la liasse que vous recopierez.</h1>
              <p className="intro-description">LMNP au réel, location longue durée. Suivez les six étapes. SoloLMNP prépare la liasse et le FEC. Il n’envoie rien aux impôts.</p>
            </section>
          )}

          {(state.kind !== "loaded" || !ready) && (
            <section id="installation" className="installation" aria-labelledby="installation-title">
              <div className="section-heading">
                <h2 id="installation-title">État de l’installation</h2>
                <button onClick={refresh} disabled={state.kind === "loading"} type="button">
                  <span aria-hidden="true">↻</span> {state.kind === "loading" ? "Vérification…" : "Actualiser"}
                </button>
              </div>
              <div aria-live="polite" aria-busy={state.kind === "loading"}>
                {state.kind === "loading" && <p className="notice">Connexion au service et vérification du stockage…</p>}
                {state.kind === "error" && (
                  <div className="notice notice-error" role="alert">
                    <strong>Connexion au service indisponible</strong>
                    <p>Vérifiez que l’application est démarrée, puis réessayez avec « Actualiser ».</p>
                  </div>
                )}
                {status && !ready && (
                  <div className="notice notice-error">
                    <strong>Le stockage nécessite une vérification</strong>
                    <p>La base n’est pas disponible ou sa migration est incomplète. Version actuelle : {status.database.schema_revision ?? "non initialisée"}. Version attendue : {status.database.expected_revision}.</p>
                  </div>
                )}
              </div>
            </section>
          )}

          {page === "overview" && ready && (
            <>
              <ol className="path-list">
                {navItems.filter((item) => item.step).map((item) => (
                  <li key={item.id}>
                    <button type="button" onClick={() => setPage(item.id)}>
                      <span className="stage-number">{item.step}</span>
                      <span className="stage-description"><strong>{item.label}</strong><span>{item.hint}</span></span>
                    </button>
                  </li>
                ))}
              </ol>
              <details className="install-details">
                <summary>Détail technique</summary>
                <p>Version {status?.application_version}. Schéma {status?.database.schema_revision}.</p>
                <button onClick={refresh} type="button">Actualiser</button>
              </details>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
