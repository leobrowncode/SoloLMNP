import { createAuthClient } from "@neondatabase/auth";
import { BetterAuthReactAdapter } from "@neondatabase/auth/react/adapters";

function client() {
  const url = import.meta.env.VITE_NEON_AUTH_URL;
  if (!url) throw new Error("L’adresse Neon Auth n’est pas configurée.");
  return createAuthClient(url, { adapter: BetterAuthReactAdapter() });
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
  const started = await auth.signIn.social({ provider: "google", callbackURL });
  if (started.error) throw failure(started.error, "La connexion Google a été refusée.");
}

export async function restoreNeonToken(): Promise<string | null> {
  if (!import.meta.env.VITE_NEON_AUTH_URL) return null;
  const auth = client();
  const session = await auth.getSession();
  if (session.error || !session.data?.user) return null;
  return jwt(auth);
}

export async function signOutNeon(): Promise<void> {
  if (!import.meta.env.VITE_NEON_AUTH_URL) return;
  const auth = client();
  await auth.signOut();
}
