import { NavLink, Outlet, useLocation } from "react-router-dom";
import { signOutNeon } from "../../api/neonAuth";
import { clearToken, localAuthMode } from "../../api/session";
import { Badge } from "../components/ui/badge";
import { libelleEtat } from "../lib/status";
import { useDossierSession } from "../context/DossierContext";
import { cn } from "../lib/cn";

const ETAPES = [
  { to: "/v1/dossier", label: "Dossier" },
  { to: "/v1/bien", label: "Bien" },
  { to: "/v1/annee", label: "Année" },
  { to: "/v1/revue", label: "Revue" },
  { to: "/v1/sorties", label: "Sorties" },
];

export default function V1Shell() {
  const { pathname } = useLocation();
  const { session } = useDossierSession();
  const etat = session?.calcul?.etat?.effectif ?? session?.dossier?.statut;
  const libelle = session?.calcul?.etat?.libelle ?? libelleEtat(String(etat ?? "brouillon"));

  return (
    <div className="min-h-screen">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-card)]">
        <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted-foreground)]">SoloLMNP v1</p>
            <h1 className="text-xl font-semibold">Saisie LMNP réel simplifié</h1>
            <p className="text-sm text-[var(--color-muted-foreground)]">
              L&apos;outil calcule, l&apos;utilisateur signe. Aucune télétransmission.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Badge>{libelle}</Badge>
            {localAuthMode() ? null : (
              <button
                type="button"
                className="text-sm underline"
                onClick={() => {
                  void signOutNeon().finally(() => {
                    clearToken();
                    window.location.assign("/connexion");
                  });
                }}
              >
                Se déconnecter
              </button>
            )}
          </div>
        </div>
        <nav className="mx-auto flex max-w-5xl gap-1 overflow-x-auto px-4 pb-3" aria-label="Étapes de saisie">
          {ETAPES.map((etape) => (
            <NavLink
              key={etape.to}
              to={etape.to}
              className={cn(
                "rounded-lg px-3 py-2 text-sm font-medium whitespace-nowrap",
                pathname === etape.to
                  ? "bg-[var(--color-primary)] text-[var(--color-primary-foreground)]"
                  : "text-[var(--color-muted-foreground)] hover:bg-[var(--color-muted)]",
              )}
            >
              {etape.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
