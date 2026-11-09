import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  googleCallbackURL,
  restoreNeonToken,
  signInWithGoogle,
  signInWithPassword,
  signOutNeon,
  signUpWithPassword,
} from "../api/neonAuth";
import { errorSummary, parseApiErrorDetail } from "../api/errors";
import { localAuthMode, neonAuthConfigured, safeNext, storeToken, testAuthMode } from "../api/session";

export default function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const search = params.toString();
  const [trackedSearch, setTrackedSearch] = useState(search);
  const [oauthSettled, setOauthSettled] = useState(false);
  const queryError = params.get("error") ? "La connexion Google a été refusée." : "";
  const returning = params.has("neon_auth_session_verifier");
  if (trackedSearch !== search) {
    setTrackedSearch(search);
    setOauthSettled(false);
  }
  const oauthPending = returning && !queryError && !oauthSettled;

  const enter = useCallback((token: string) => {
    storeToken(token);
    navigate(next, { replace: true });
  }, [navigate, next]);

  const ensureAdmitted = useCallback(async (address: string): Promise<boolean> => {
    const query = new URLSearchParams({ email: address.trim() });
    const response = await fetch(`/api/auth/admission?${query}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (response.status === 403) {
      setError(
        "Cette adresse n’est pas autorisée. L’inscription est réservée aux adresses déjà invitées.",
      );
      return false;
    }
    if (!response.ok) {
      const body = await response.json().catch(() => undefined) as { detail?: unknown } | undefined;
      const detail = parseApiErrorDetail(body?.detail);
      setError(detail.message ? errorSummary(detail) : "L’adresse n’a pas pu être vérifiée.");
      return false;
    }
    return true;
  }, []);

  const admit = useCallback(async (token: string): Promise<boolean> => {
    const allowed = await fetch("/api/status", {
      cache: "no-store",
      headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
    });
    if (allowed.status === 403) {
      await signOutNeon();
      setError("Cette adresse n’est pas autorisée.");
      return false;
    }
    if (!allowed.ok && allowed.status !== 503) {
      setError("La session n’a pas été acceptée.");
      return false;
    }
    enter(token);
    return true;
  }, [enter]);

  useEffect(() => {
    if (localAuthMode() || testAuthMode() || !neonAuthConfigured() || queryError) return;
    let cancelled = false;
    restoreNeonToken(search)
      .then(async (token) => {
        if (cancelled) return;
        if (!token) {
          if (returning) setError("La connexion Google a été refusée.");
          return;
        }
        await admit(token);
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(caught instanceof Error && caught.message ? caught.message : "La connexion Google a été refusée.");
        }
      })
      .finally(() => {
        if (!cancelled) setOauthSettled(true);
      });
    return () => {
      cancelled = true;
    };
  }, [admit, queryError, returning, search]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      if (testAuthMode()) {
        const expectedEmail = import.meta.env.VITE_TEST_USER_EMAIL ?? "";
        const expectedPassword = import.meta.env.VITE_TEST_USER_PASSWORD ?? "";
        const token = import.meta.env.VITE_TEST_TOKEN ?? "";
        if (
          email.trim().toLowerCase() !== expectedEmail.toLowerCase()
          || password !== expectedPassword
          || !token
        ) {
          setError("Adresse ou mot de passe refusé.");
          return;
        }
        enter(token);
        return;
      }
      if (!neonAuthConfigured()) {
        setError("L’authentification n’est pas configurée.");
        return;
      }
      const address = email.trim();
      if (creating && !(await ensureAdmitted(address))) {
        return;
      }
      const token = creating
        ? await signUpWithPassword(address, password, name.trim())
        : await signInWithPassword(address, password);
      await admit(token);
    } catch (caught) {
      setError(caught instanceof Error && caught.message ? caught.message : "Connexion refusée.");
    } finally {
      setPending(false);
    }
  }

  async function onGoogle() {
    setError("");
    setPending(true);
    try {
      await signInWithGoogle(googleCallbackURL(next, window.location.origin));
    } catch (caught) {
      setError(caught instanceof Error && caught.message ? caught.message : "La connexion Google a été refusée.");
      setPending(false);
    }
  }

  if (localAuthMode()) {
    return (
      <main className="login-screen" id="main">
        <section className="login-card">
          <p className="login-brand">SoloLMNP</p>
          <h1 id="page-title">Dossier local</h1>
          <p className="login-lead">
            Un seul dossier sur cette machine, sans compte Neon. Les données restent dans SQLite.
          </p>
          <button type="button" onClick={() => navigate(next)}>Ouvrir le dossier</button>
        </section>
      </main>
    );
  }

  if (!testAuthMode() && !neonAuthConfigured()) {
    return (
      <main className="login-screen" id="main">
        <section className="login-card">
          <p className="login-brand">SoloLMNP</p>
          <h1 id="page-title">Authentification non configurée</h1>
          <p className="login-lead">
            Neon Auth n’a pas d’adresse. Le formulaire de connexion ne peut pas ouvrir le dossier.
          </p>
          <p className="login-note">
            Pour un essai sur cette machine, le lanceur et Docker utilisent le mode local
            (AUTH_MODE=local et VITE_AUTH_MODE=local), sans secret. Ce mode est refusé
            quand APP_ENV vaut production, et sur Vercel.
          </p>
          <p className="login-note">
            Pour brancher Neon : NEON_AUTH_BASE_URL, VITE_NEON_AUTH_URL et ALLOWED_EMAILS.
            Le détail est dans docs/DEPLOYMENT.md.
          </p>
          <p className="login-note">
            <a href="https://github.com/leobrowncode/SoloLMNP/blob/main/docs/DEPLOYMENT.md">
              Documentation de déploiement
            </a>
            {" · "}
            <a href="https://sololmnp.vercel.app">Instance hébergée</a>
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="login-screen" id="main">
      <form className="login-card" onSubmit={(event) => { void onSubmit(event); }}>
        <p className="login-brand">SoloLMNP</p>
        <h1 id="page-title">Connexion</h1>
        <p className="login-lead">Le dossier reste privé. Seules les adresses autorisées entrent.</p>
        {creating && (
          <p className="login-note">
            L’inscription est réservée aux adresses déjà invitées. Si la vôtre n’est pas sur la liste,
            aucun compte ne sera créé chez Neon Auth.
          </p>
        )}
        {creating && (
          <label className="form-field">
            Nom
            <input value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" required />
          </label>
        )}
        <label className="form-field">
          Adresse e-mail
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label className="form-field">
          Mot de passe
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete={creating ? "new-password" : "current-password"}
            minLength={8}
            required
            aria-describedby={creating ? "password-min-length" : undefined}
          />
          {creating && <span id="password-min-length" className="form-help">8 caractères minimum.</span>}
        </label>
        {(error || queryError) && <p className="notice notice-error" role="alert">{error || queryError}</p>}
        <button type="submit" disabled={pending || oauthPending}>
          {pending || oauthPending ? "Connexion…" : creating ? "Créer le compte" : "Se connecter"}
        </button>
        <button type="button" className="login-switch" onClick={() => { setCreating((value) => !value); setError(""); }}>
          {creating ? "J’ai déjà un compte" : "Créer un compte"}
        </button>
        {testAuthMode() ? (
          <p className="login-note">Google n’est pas disponible dans le mode d’essai.</p>
        ) : (
          <button type="button" onClick={() => { void onGoogle(); }} disabled={pending || oauthPending || !neonAuthConfigured()}>
            Continuer avec Google
          </button>
        )}
      </form>
    </main>
  );
}
