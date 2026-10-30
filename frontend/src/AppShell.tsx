import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { fetchStatus } from "./api/status";
import { MOBILE_QUERY, NARROW_CONTROL_QUERY, useMediaQuery } from "./lib/viewport";
import { focusRouteTarget } from "./routing/focusTarget";
import { navItems, pageIdFromPathname, ROUTES, viewDocumentTitle, type PageId } from "./routing/paths";
import { UnsavedChangesProvider } from "./routing/unsaved";
import DossierProgress from "./features/DossierProgress";
import DossierStatus from "./features/DossierStatus";
import GlossaryTip from "./features/GlossaryTip";
import OverviewDashboard from "./features/OverviewDashboard";
import { showsDossierIndicator, showsOperationalStorage } from "./features/dossierStatus";
import ScreenStatus from "./features/ScreenStatus";
import { showsLoading } from "./features/screenState";
import { useScreenQuery } from "./features/useScreenQuery";

const SERVICE_DOWN = {
  code: "SERVICE_UNAVAILABLE",
  message: "Connexion au service indisponible. Vérifiez que l’application est démarrée, puis réessayez.",
};

function publishViewTitle(label: string) {
  document.title = viewDocumentTitle(label);
}

function focusElement(target: HTMLElement) {
  try {
    target.focus({ preventScroll: true });
  } catch {
    target.focus();
  }
}

function focusMain() {
  const main = document.getElementById("main");
  if (main instanceof HTMLElement) focusElement(main);
}

function focusPageHeading() {
  const heading = document.getElementById("page-title");
  if (!(heading instanceof HTMLElement)) return;
  const active = document.activeElement;
  if (active instanceof HTMLElement && active.closest(".local-feedback, .save-highlight")) return;
  focusElement(heading);
}

function focusCurrentRoute(hash: string) {
  let stopped = false;
  const started = performance.now();
  function tick() {
    if (stopped) return;
    if (focusRouteTarget(hash)) return;
    if (performance.now() - started > 4000) {
      focusPageHeading();
      return;
    }
    window.setTimeout(tick, 50);
  }
  tick();
  return () => { stopped = true; };
}

export default function AppShell() {
  const { state, retry } = useScreenQuery(fetchStatus, "status", {
    keepPrevious: true,
    mapError: () => SERVICE_DOWN,
  });
  const location = useLocation();
  const page: PageId = pageIdFromPathname(location.pathname);
  const mobileNav = useMediaQuery(MOBILE_QUERY);
  const narrowControls = useMediaQuery(NARROW_CONTROL_QUERY);
  const [navState, setNavState] = useState({ path: location.pathname, open: false });
  if (navState.path !== location.pathname) {
    setNavState({ path: location.pathname, open: false });
  }
  const navOpen = navState.open;
  function setNavOpen(open: boolean) {
    setNavState({ path: location.pathname, open });
  }

  const activeNav = navItems.find((item) => item.id === page);
  const pageTitle = activeNav?.label ?? "SoloLMNP";

  useEffect(() => {
    publishViewTitle(pageTitle);
  }, [pageTitle]);

  const focusedView = useRef<PageId | null>(null);
  useEffect(() => {
    const viewChanged = focusedView.current !== page;
    focusedView.current = page;
    if (!viewChanged || location.hash) return;
    focusPageHeading();
  }, [page, location.hash]);

  useEffect(() => {
    if (!location.hash) return undefined;
    return focusCurrentRoute(location.hash);
  }, [location.pathname, location.hash]);
  useEffect(() => {
    if (!navOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setNavState((current) => ({ ...current, open: false }));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen]);

  const status = state.data;
  const serviceReady = status?.database.status === "ready";
  const dossier = status?.dossier;
  const liveDossier = showsDossierIndicator(state.phase, serviceReady, dossier) ? dossier : null;
  const showProgress = state.phase === "loaded" && Boolean(serviceReady);
  const storageLive = showsOperationalStorage(state.phase, serviceReady);
  const showWorkspace = Boolean(serviceReady) && (
    state.phase === "loaded" || state.phase === "loading" || state.stale
  );
  const showInstall = !showWorkspace || state.phase === "error" || Boolean(status && !serviceReady);

  let workspace: ReactNode = null;
  if (showWorkspace && page !== "overview") {
    workspace = <Outlet />;
  }

  const menuOpen = !mobileNav || navOpen;

  function renderNavLink(item: (typeof navItems)[number], className?: string) {
    return (
      <NavLink
        key={item.id}
        to={item.path}
        end={item.id === "overview"}
        className={({ isActive }) => [isActive ? "nav-active" : undefined, className].filter(Boolean).join(" ") || undefined}
        onClick={() => {
          setNavOpen(false);
        }}
      >
        {item.step ? <span className="nav-step" aria-hidden="true">{item.step}</span> : <span aria-hidden="true">◫</span>}
        {item.label}
      </NavLink>
    );
  }

  return (
    <UnsavedChangesProvider>
      <div className={narrowControls ? "app-layout narrow-controls" : "app-layout"}>
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
          <Link to={ROUTES.home} className="brand" aria-label="SoloLMNP — accueil">
            <span className="brand-mark" aria-hidden="true">S</span>
            <span>Solo<span className="brand-light">LMNP</span></span>
          </Link>
          <p className="sidebar-label">PARCOURS DÉCLARATIF</p>
          <nav aria-label="Navigation principale">
            {mobileNav && (
              <button
                type="button"
                className="nav-toggle"
                aria-expanded={navOpen}
                aria-controls="primary-nav-links"
                onClick={() => setNavOpen(!navOpen)}
              >
                {navOpen ? "Replier le menu" : "Ouvrir le menu"}
              </button>
            )}
            {mobileNav && !navOpen && activeNav && renderNavLink(activeNav, "nav-current")}
            <div id="primary-nav-links" className="nav-links" {...(menuOpen ? {} : { hidden: true })}>
              {navItems.map((item) => renderNavLink(item))}
            </div>
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
            <p id="route-announcement" className="sr-only" aria-live="polite" aria-atomic="true">{pageTitle}</p>
            <h1 id="page-title" className="topbar-title" tabIndex={-1}>{pageTitle}</h1>
            <div className="topbar-meta">
              {liveDossier && <DossierStatus dossier={liveDossier} />}
              {showProgress && <DossierProgress />}
            </div>
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
                <h2 id="welcome-title">De l’écriture à la liasse que vous recopierez.</h2>
                <p className="intro-description">LMNP au réel, location longue durée. Le menu sert à naviguer. Ici, chaque étape du dossier indique son état. SoloLMNP prépare la liasse et le FEC. Il n’envoie rien aux impôts.</p>
                <div className="heading-with-help">
                  <GlossaryTip id="lmnp-reel" />
                  <GlossaryTip id="liasse" />
                  <GlossaryTip id="fec" />
                </div>
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

            {page === "overview" && showWorkspace && state.phase !== "error" && (
              <OverviewDashboard />
            )}

            {page === "overview" && showWorkspace && (
              <>
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
