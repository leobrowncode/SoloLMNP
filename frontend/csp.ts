export function contentSecurityPolicy(authUrl: string): string {
  const origin = neonAuthOrigin(authUrl);
  const connect = ["'self'", origin, "https://vercel.com"]
    .filter((part) => part.length > 0)
    .join(" ");
  return [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    `connect-src ${connect}`,
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

function neonAuthOrigin(authUrl: string): string {
  const trimmed = authUrl.trim();
  if (!trimmed) return "";
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error("VITE_NEON_AUTH_URL n’est pas une URL.");
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    throw new Error("VITE_NEON_AUTH_URL doit être http(s).");
  }
  if (parsed.username || parsed.password) {
    throw new Error("VITE_NEON_AUTH_URL ne doit pas contenir de secret.");
  }
  return parsed.origin;
}
