import { useEffect, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { fetchStatus } from "./api/status";
import { navItems, pageIdFromPathname, ROUTES, type PageId } from "./routing/paths";
import { UnsavedChangesProvider } from "./routing/unsaved";
import DossierStatus from "./features/DossierStatus";
import { showsDossierIndicator, showsOperationalStorage } from "./features/dossierStatus";
import ScreenStatus from "./features/ScreenStatus";
import { showsLoading } from "./features/screenState";
import { useScreenQuery } from "./features/useScreenQuery";

const SERVICE_DOWN = {
  code: "SERVICE_UNAVAILABLE",
  message: "Connexion au service indisponible. Vérifiez que l’application est démarrée, puis réessayez.",
};

function focusMain() {
  document.getElementById("main")?.focus();
}

export default function AppShell() {
  const { state, retry } = useScreenQuery(fetchStatus, "status", {
    keepPrevious: true,
    mapError: () => SERVICE_DOWN,
  });
  const location = useLocation();
  const page: PageId = pageIdFromPathname(location.pathname);

  useEffect(() => {
    focusMain();
  }, [location.pathname]);

  const status = state.data;
  const serviceReady = status?.database.status === "ready";
  const dossier = status?.dossier;
  const liveDossier = showsDossierIndicator(state.phase, serviceReady, dossier) ? dossier : null;
  const storageLive = showsOperationalStorage(state.phase, serviceReady);
  const showWorkspace = Boolean(serviceReady) && (
    state.phase === "loaded" || state.phase === "loading" || state.stale
  );
  const showInstall = !showWorkspace || state.phase === "error" || Boolean(status && !serviceReady);

  let workspace: ReactNode = null;
  if (showWorkspace && page !== "overview") {
    workspace = <Outlet />;
  }

  const activeNav = navItems.find((item) => item.id === page);

  return (
    <UnsavedChangesProvider>
      <div className="app-layout">
        <a
          className="skip-link"
          href="#main"
          onClick={(event) => {
            event.preventDefault();
            focusMain();
          }}
        >
          Aller au contenu
        </a>
        <aside className="sidebar">
          <Link to={ROUTES.home} className="brand" aria-label="SoloLMNP — accueil" onClick={focusMain}>
            <span className="brand-mark" aria-hidden="true">S</span>
            <span>Solo<span className="brand-light">LMNP</span></span>
          </Link>
          <p className="sidebar-label">PARCOURS DÉCLARATIF</p>
          <nav aria-label="Navigation principale">
            {navItems.map((item) => (
              <NavLink
                key={item.id}
                to={item.path}
                end={item.id === "overview"}
                className={({ isActive }) => (isActive ? "nav-active" : undefined)}
                onClick={focusMain}
              >
                {item.step ? <span className="nav-step" aria-hidden="true">{item.step}</span> : <span aria-hidden="true">◫</span>}
                {item.label}
              </NavLink>
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
            <p className="topbar-title">{activeNav?.label}</p>
            {liveDossier && <DossierStatus dossier={liveDossier} />}
          </header>
          <div className="content">
            {status?.storage_warning && (
              <div className="notice notice-error" role="alert">
                <strong>Stockage non sûr</strong>
                <p>{status.storage_warning}</p>
              </div>
            )}
            {workspace}

            {page === "overview" && showWorkspace && (
              <section className="intro" aria-labelledby="welcome-title">
                <h1 id="welcome-title">De l’écriture à la liasse que vous recopierez.</h1>
                <p className="intro-description">LMNP au réel, location longue durée. Suivez les six étapes. SoloLMNP prépare la liasse et le FEC. Il n’envoie rien aux impôts.</p>
              </section>
            )}

            {showInstall && (
              <section id="installation" className="installation" aria-labelledby="installation-title" data-screen-phase={state.phase}>
                <div className="section-heading">
                  <h2 id="installation-title">État de l’installation</h2>
                  <button onClick={retry} disabled={state.phase === "loading"} type="button">
                    <span aria-hidden="true">↻</span> {state.phase === "loading" ? "Vérification…" : "Actualiser"}
                  </button>
                </div>
                <div aria-live="polite" aria-busy={state.phase === "loading"}>
                  {showsLoading(state) && <p className="notice">Connexion au service et vérification du stockage…</p>}
                  <ScreenStatus state={state} onRetry={retry} className="notice notice-error" />
                  {status && !serviceReady && state.phase !== "error" && (
                    <div className="notice notice-error">
                      <strong>Le stockage nécessite une vérification</strong>
                      <p>La base n’est pas disponible ou sa migration est incomplète. Version actuelle : {status.database.schema_revision ?? "non initialisée"}. Version attendue : {status.database.expected_revision}.</p>
                    </div>
                  )}
                </div>
              </section>
            )}

            {page === "overview" && showWorkspace && (
              <>
                <ol className="path-list">
                  {navItems.filter((item) => item.step).map((item) => (
                    <li key={item.id}>
                      <Link to={item.path} className="path-link" onClick={focusMain}>
                        <span className="stage-number">{item.step}</span>
                        <span className="stage-description"><strong>{item.label}</strong><span>{item.hint}</span></span>
                      </Link>
                    </li>
                  ))}
                </ol>
                {storageLive && (
                  <details className="install-details" data-diagnostic="storage">
                    <summary>Diagnostic technique</summary>
                    <p><strong>Stockage opérationnel</strong>. Version {status?.application_version}. Schéma {status?.database.schema_revision}.</p>
                    <button onClick={retry} type="button">Actualiser</button>
                  </details>
                )}
              </>
            )}
          </div>
        </main>
      </div>
    </UnsavedChangesProvider>
  );
}
