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

const navItems: { id: PageId; label: string; step?: string }[] = [
  { id: "overview", label: "Vue d’ensemble" },
  { id: "ledger", label: "Comptabilité", step: "1" },
  { id: "operations", label: "Opérations & banque", step: "2" },
  { id: "assets", label: "Immobilisations", step: "3" },
  { id: "statements", label: "États comptables", step: "4–5" },
  { id: "fiscal", label: "Fiscalité LMNP", step: "6" },
  { id: "conservation", label: "Conservation", step: "7" },
];

const stages = [
  ["01", "Fondations", "Configuration, stockage exact, migrations et contrôles techniques.", "Disponible"],
  ["02", "Comptabilité", "Écritures en partie double, journal, grand livre et balance.", "Disponible"],
  ["03", "Opérations", "Recettes, dépenses, imports CSV, rapprochement et emprunts.", "Disponible"],
  ["04", "Immobilisations", "Registre, composants, prorata et dotations comptables.", "Disponible"],
  ["05", "États comptables", "Rubriques, centralisation, affectation et continuité.", "Disponible"],
  ["06–10", "Fiscalité & déclaration", "Liasse à recopier sur impots.gouv.fr et FEC pour un contrôle. Aucun envoi.", "Recopie"],
  ["11–12", "Conservation & fiabilité", "Justificatifs, sauvegarde, restauration et parcours A à J.", "Disponible"],
];

export default function App() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [page, setPage] = useState<PageId>("ledger");
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
          <a href="#installation"><span aria-hidden="true">◎</span> État de l’installation</a>
        </nav>
        <div className="sidebar-note">
          <span className="small-dot" aria-hidden="true" />
          <strong>Ordre recommandé</strong>
          <p>Comptabilité → opérations → immobilisations → états → fiscal → conservation. Voir docs/TUTORIAL.md.</p>
        </div>
        <div className="sidebar-version">SoloLMNP · {status ? `v${status.application_version}` : "Développement"}</div>
      </aside>

      <main id="main" tabIndex={-1}>
        <header className="topbar">
          <span>ESPACE DE GESTION</span>
        </header>
        <div className="content">
          {workspace}

          {(page === "overview" || !ready) && (
            <section className="intro" aria-labelledby="welcome-title">
              <p className="eyebrow">UNE COMPTABILITÉ QUE VOUS POURREZ EXPLIQUER</p>
              <h1 id="welcome-title">De l’écriture à la liasse<br /><span>que vous recopierez.</span></h1>
              <p className="intro-description">LMNP au réel, location longue durée, plusieurs locataires. SoloLMNP prépare la liasse et le FEC. Il n’envoie rien aux impôts.</p>
            </section>
          )}

          <section id="installation" className="installation" aria-labelledby="installation-title">
            <div className="section-heading">
              <div><p className="eyebrow">DIAGNOSTIC EN DIRECT</p><h2 id="installation-title">État de l’installation</h2></div>
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
              {status?.storage_warning && (
                <p className="notice" role="status">{status.storage_warning}</p>
              )}
              {status && (
                <>
                  <div className={ready ? "connection-summary" : "notice notice-error"}>
                    <span className="status-dot" aria-hidden="true" />
                    <div><strong>{ready ? "Le socle technique répond correctement" : "Le stockage nécessite une vérification"}</strong>
                    <p>{ready ? "Service accessible et schéma de données à jour." : "La base n’est pas disponible ou sa migration est incomplète. Consultez le guide d’installation du dépôt."}</p></div>
                  </div>
                  <div className="status-grid">
                    <article className="status-card">
                      <span className="card-index">01 / SERVICE</span>
                      <h3>Application</h3><p className="card-value">Connectée <span aria-hidden="true">↗</span></p>
                      <p>Version {status.application_version}</p>
                    </article>
                    <article className="status-card">
                      <span className="card-index">02 / STOCKAGE</span>
                      <h3>Base SQLite</h3><p className="card-value">{ready ? "Prête" : "À vérifier"}</p>
                      <p>{ready ? "Migration appliquée et tables présentes." : "Aucune opération comptable disponible."}</p>
                      <details><summary>Détail du schéma</summary><p>Version actuelle : <code>{status.database.schema_revision ?? "Non initialisée"}</code><br />Version attendue : <code>{status.database.expected_revision}</code></p></details>
                    </article>
                    <article className="status-card">
                      <span className="card-index">03 / FISCALITÉ</span>
                      <h3>Règles fiscales</h3><p className="card-value card-muted">Recopie</p>
                      <p>La liasse se recopie dans l’espace professionnel. Aucun envoi n’est effectué.</p>
                    </article>
                  </div>
                </>
              )}
            </div>
          </section>

          {page === "overview" && (
            <>
              <section className="scope-note" aria-label="Périmètre disponible">
                <span className="scope-icon" aria-hidden="true">i</span>
                <div><h2>Ce que permet cette version</h2>
                <p>Tenir la comptabilité d’une colocation meublée, clôturer, télécharger le FEC et recopier la liasse. SoloLMNP n’envoie rien aux impôts.</p></div>
              </section>

              <section id="roadmap" className="roadmap" aria-labelledby="roadmap-title">
                <div className="section-heading"><div><p className="eyebrow">DANS LE BON ORDRE</p><h2 id="roadmap-title">De l’écriture à la déclaration</h2></div><span className="subtle">Un socle vérifié à chaque étape</span></div>
                <ol className="stage-list">{stages.map(([number, title, description, label]) => (
                  <li key={number}><span className="stage-number">{number}</span><div className="stage-description"><h3>{title}</h3><p>{description}</p></div><span className={number === "01" ? "stage-label current" : "stage-label"}>{label}</span></li>
                ))}</ol>
              </section>
            </>
          )}
          <footer>Comptabilité d’abord. Fiscalité sourcée. Données sous votre contrôle.</footer>
        </div>
      </main>
    </div>
  );
}
