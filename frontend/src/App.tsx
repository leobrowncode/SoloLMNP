import { useEffect, useState } from "react";
import { fetchStatus, type ApplicationStatus } from "./api/status";

type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "loaded"; data: ApplicationStatus };

const stages = [
  ["01", "Fondations", "Configuration, stockage exact, migrations et contrôles techniques.", "En cours de validation"],
  ["02", "Comptabilité", "Écritures en partie double, journal, grand livre et balance.", "Prochaine étape"],
  ["03–05", "Gestion & états", "Opérations, immobilisations, amortissements et états comptables.", "À développer"],
  ["06–10", "Fiscalité & déclaration", "Règles sourcées, reports, clôture, FEC et préparation de la saisie EFI.", "À développer"],
  ["11–12", "Conservation & fiabilité", "Justificatifs, sauvegarde, restauration et parcours complets.", "À développer"],
];

export default function App() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
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

  return (
    <div className="app-layout">
      <a className="skip-link" href="#main">Aller au contenu</a>
      <aside className="sidebar">
        <a href="#main" className="brand" aria-label="SoloLMNP — accueil">
          <span className="brand-mark" aria-hidden="true">S</span>
          <span>Solo<span className="brand-light">LMNP</span></span>
        </a>
        <p className="sidebar-label">VOTRE ESPACE LOCAL</p>
        <nav aria-label="Navigation principale">
          <a href="#main" className="nav-active"><span aria-hidden="true">◫</span> Vue d’ensemble</a>
          <a href="#installation"><span aria-hidden="true">◎</span> État de l’installation</a>
          <a href="#roadmap"><span aria-hidden="true">↗</span> Étapes du projet</a>
        </nav>
        <div className="sidebar-note">
          <span className="small-dot" aria-hidden="true" />
          <strong>Une instance, vos données.</strong>
          <p>Conçu pour un usage personnel, en local ou sur un hébergement privé.</p>
        </div>
        <div className="sidebar-version">SoloLMNP · {status ? `v${status.application_version}` : "Développement"}</div>
      </aside>

      <main id="main" tabIndex={-1}>
        <header className="topbar">
          <span>ESPACE DE GESTION</span>
          <span className="phase-badge">Phase 1 · Fondations</span>
        </header>
        <div className="content">
          <section className="intro" aria-labelledby="welcome-title">
            <p className="eyebrow">UNE COMPTABILITÉ QUE VOUS POURREZ EXPLIQUER</p>
            <h1 id="welcome-title">Les bonnes bases,<br /><span>avant les premiers chiffres.</span></h1>
            <p className="intro-description">Votre espace LMNP se construit autour d’une comptabilité traçable. Cette première étape vérifie que l’application et son stockage sont prêts pour la suite.</p>
          </section>

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
                      <h3>Règles fiscales</h3><p className="card-value card-muted">En recherche</p>
                      <p>Aucun millésime utilisable pour une déclaration à ce stade.</p>
                    </article>
                  </div>
                </>
              )}
            </div>
          </section>

          <section className="scope-note" aria-label="Périmètre disponible">
            <span className="scope-icon" aria-hidden="true">i</span>
            <div><h2>Ce que permet cette version</h2>
            <p>Vérifier les fondations techniques. La saisie des opérations, les calculs comptables, le FEC et la liasse fiscale seront ajoutés dans les prochaines phases. Aucun montant déclarable n’est produit aujourd’hui.</p></div>
          </section>

          <section id="roadmap" className="roadmap" aria-labelledby="roadmap-title">
            <div className="section-heading"><div><p className="eyebrow">DANS LE BON ORDRE</p><h2 id="roadmap-title">De l’écriture à la déclaration</h2></div><span className="subtle">Un socle vérifié à chaque étape</span></div>
            <ol className="stage-list">{stages.map(([number, title, description, label]) => (
              <li key={number}><span className="stage-number">{number}</span><div className="stage-description"><h3>{title}</h3><p>{description}</p></div><span className={number === "01" ? "stage-label current" : "stage-label"}>{label}</span></li>
            ))}</ol>
          </section>
          <footer>Comptabilité d’abord. Fiscalité sourcée. Données sous votre contrôle.</footer>
        </div>
      </main>
    </div>
  );
}
