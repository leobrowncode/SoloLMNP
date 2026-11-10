const TOKEN_KEY = "sololmnp.token";

export function readToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function storeToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(extra?: HeadersInit): Headers {
  const headers = new Headers(extra);
  const token = readToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

const LEGACY_HOME = "/legacy";

export function safeNext(value: string | null): string {
  if (!value || value.startsWith("//") || value.startsWith("/connexion")) {
    return LEGACY_HOME;
  }
  if (value === "/" || !value.startsWith("/")) {
    return LEGACY_HOME;
  }
  return value;
}

export function loginPath(next: string): string {
  const target = safeNext(next);
  return target === LEGACY_HOME ? "/connexion" : `/connexion?next=${encodeURIComponent(target)}`;
}

/** Drop a dead session. Vitest keeps the current page so a mocked 401 stays an error. */
export function noteUnauthorized(status: number): void {
  if (status !== 401) return;
  clearToken();
  if (import.meta.env.MODE === "test") return;
  if (window.location.pathname.startsWith("/connexion")) return;
  const next = window.location.pathname + window.location.search + window.location.hash;
  window.location.assign(loginPath(next));
}

export function testAuthMode(): boolean {
  return import.meta.env.VITE_AUTH_MODE === "test";
}

/** One local dossier, baked in only when the dev server or image is built that way. */
export function localAuthMode(): boolean {
  return import.meta.env.VITE_AUTH_MODE === "local";
}

export function neonAuthConfigured(): boolean {
  return Boolean(import.meta.env.VITE_NEON_AUTH_URL);
}
