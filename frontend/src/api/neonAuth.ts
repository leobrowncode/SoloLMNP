import { createAuthClient } from "@neondatabase/auth";
import { BetterAuthReactAdapter } from "@neondatabase/auth/react/adapters";

const SESSION_VERIFIER = "neon_auth_session_verifier";

function client() {
  const url = import.meta.env.VITE_NEON_AUTH_URL;
  if (!url) throw new Error("L’adresse Neon Auth n’est pas configurée.");
  // Cross-origin SPA: the session cookie is on the Neon Auth host.
  return createAuthClient(url, {
    adapter: BetterAuthReactAdapter({ fetchOptions: { credentials: "include" } }),
  });
}

export function googleCallbackURL(next: string, origin: string): string {
  const url = new URL("/connexion", origin);
  if (next !== "/") url.searchParams.set("next", next);
  return url.toString();
}

function failure(error: unknown, fallback: string): Error {
  if (error && typeof error === "object" && "message" in error && typeof error.message === "string" && error.message) {
    return new Error(error.message);
  }
  return new Error(fallback);
}

async function jwt(auth: ReturnType<typeof client>): Promise<string> {
  const issued = await auth.token();
  const token = issued.data?.token;
  if (issued.error || typeof token !== "string" || !token) {
    throw failure(issued.error, "Le jeton de session est absent.");
  }
  return token;
}

export async function signInWithPassword(email: string, password: string): Promise<string> {
  const auth = client();
  const signed = await auth.signIn.email({ email, password });
  if (signed.error) throw failure(signed.error, "Connexion refusée.");
  return jwt(auth);
}

export async function signUpWithPassword(email: string, password: string, name: string): Promise<string> {
  const auth = client();
  const created = await auth.signUp.email({ email, password, name });
  if (created.error) throw failure(created.error, "Création du compte refusée.");
  return jwt(auth);
}

export async function signInWithGoogle(callbackURL: string): Promise<void> {
  const auth = client();
  const started = await auth.signIn.social({
    provider: "google",
    callbackURL,
    errorCallbackURL: callbackURL,
  });
  if (started.error) throw failure(started.error, "La connexion Google a été refusée.");
}

function verifierFrom(search: string): string | null {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const direct = params.get(SESSION_VERIFIER);
  if (direct) return direct;
  const next = params.get("next");
  if (!next || !next.startsWith("/") || next.startsWith("//")) return null;
  return new URL(next, "https://sololmnp.local").searchParams.get(SESSION_VERIFIER);
}

function jwtFromSession(session: { token?: unknown } | null | undefined): string | null {
  const token = session?.token;
  if (typeof token !== "string") return null;
  const parts = token.split(".");
  if (parts.length !== 3 || parts.some((part) => part.length === 0)) return null;
  return token;
}

async function jwtFromEndpoint(authUrl: string): Promise<string> {
  const base = authUrl.endsWith("/") ? authUrl : `${authUrl}/`;
  const response = await fetch(new URL("token", base), {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("Le jeton de session est absent.");
  const body: unknown = await response.json();
  const token = body && typeof body === "object" && "token" in body ? body.token : null;
  if (typeof token !== "string" || token.split(".").length !== 3) {
    throw new Error("Le jeton de session est absent.");
  }
  return token;
}

export async function restoreNeonToken(search = ""): Promise<string | null> {
  const authUrl = import.meta.env.VITE_NEON_AUTH_URL;
  if (!authUrl) return null;
  const auth = client();
  const verifier = verifierFrom(search);
  // getSession writes set-auth-jwt onto session.token. auth.token() is then
  // served from that session cache and its payload has no data.token.
  const session = await auth.getSession(verifier
    ? { query: { [SESSION_VERIFIER]: verifier } } as NonNullable<Parameters<typeof auth.getSession>[0]>
    : undefined);
  if (session.error || !session.data?.user) return null;
  const embedded = jwtFromSession(session.data.session);
  if (embedded) return embedded;
  return jwtFromEndpoint(authUrl);
}

export async function signOutNeon(): Promise<void> {
  if (!import.meta.env.VITE_NEON_AUTH_URL) return;
  const auth = client();
  await auth.signOut();
}
