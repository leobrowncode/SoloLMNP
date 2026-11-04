import { type FormEvent, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { signInWithGoogle, signInWithPassword, signUpWithPassword } from "../api/neonAuth";
import { neonAuthConfigured, safeNext, storeToken, testAuthMode } from "../api/session";

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

  function enter(token: string) {
    storeToken(token);
    navigate(next, { replace: true });
  }

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
      const token = creating
        ? await signUpWithPassword(email.trim(), password, name.trim())
        : await signInWithPassword(email.trim(), password);
      const allowed = await fetch("/api/status", {
        cache: "no-store",
        headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
      });
      if (allowed.status === 403) {
        const { signOutNeon } = await import("../api/neonAuth");
        await signOutNeon();
        setError("Cette adresse n’est pas autorisée.");
        return;
      }
      if (!allowed.ok && allowed.status !== 503) {
        setError("La session n’a pas été acceptée.");
        return;
      }
      enter(token);
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
      const callback = new URL(next, window.location.origin).toString();
      await signInWithGoogle(callback);
    } catch (caught) {
      setError(caught instanceof Error && caught.message ? caught.message : "La connexion Google a été refusée.");
      setPending(false);
    }
  }

  return (
    <main className="login-screen" id="main">
      <form className="login-card" onSubmit={(event) => { void onSubmit(event); }}>
        <p className="login-brand">SoloLMNP</p>
        <h1 id="page-title">Connexion</h1>
        <p className="login-lead">Le dossier reste privé. Seules les adresses autorisées entrent.</p>
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
          />
        </label>
        {error && <p className="notice notice-error" role="alert">{error}</p>}
        <button type="submit" disabled={pending}>
          {pending ? "Connexion…" : creating ? "Créer le compte" : "Se connecter"}
        </button>
        <button type="button" className="login-switch" onClick={() => { setCreating((value) => !value); setError(""); }}>
          {creating ? "J’ai déjà un compte" : "Créer un compte"}
        </button>
        {testAuthMode() ? (
          <p className="login-note">Google n’est pas disponible dans le mode d’essai.</p>
        ) : (
          <button type="button" onClick={() => { void onGoogle(); }} disabled={pending || !neonAuthConfigured()}>
            Continuer avec Google
          </button>
        )}
      </form>
    </main>
  );
}
