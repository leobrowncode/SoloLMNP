import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { googleCallbackURL, restoreNeonToken, signInWithPassword, signOutNeon } from "./neonAuth";

const AUTH = "https://auth.example.test/neondb/auth";

type Call = { url: string; credentials?: RequestCredentials | undefined; method?: string | undefined };

function user() {
  const now = new Date().toISOString();
  return {
    id: "user-1",
    email: "ada@example.com",
    name: "Ada",
    emailVerified: true,
    createdAt: now,
    updatedAt: now,
  };
}

function sessionBody(token: string) {
  return {
    session: {
      id: "session-1",
      token,
      userId: "user-1",
      expiresAt: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    },
    user: user(),
  };
}

describe("neon auth", () => {
  let calls: Call[];

  beforeEach(() => {
    calls = [];
    vi.stubEnv("VITE_AUTH_MODE", "");
    vi.stubEnv("VITE_NEON_AUTH_URL", AUTH);
    vi.stubGlobal("fetch", vi.fn(async () => new Response("null", {
      status: 200,
      headers: { "content-type": "application/json" },
    })));
  });

  afterEach(async () => {
    await signOutNeon();
  });

  function installFetch(handler: (url: string, init: RequestInit | undefined) => Response | Promise<Response>) {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push({ url, credentials: init?.credentials, method: init?.method });
      return Promise.resolve(handler(url, init));
    }));
  }

  it("construit le retour Google sur /connexion", () => {
    expect(googleCallbackURL("/", "https://sololmnp.vercel.app")).toBe("https://sololmnp.vercel.app/connexion");
    expect(googleCallbackURL("/comptabilite/journal", "https://sololmnp.vercel.app")).toBe(
      "https://sololmnp.vercel.app/connexion?next=%2Fcomptabilite%2Fjournal",
    );
  });

  it("reprend le JWT déjà posé sur la session, sans /token", async () => {
    installFetch((url) => {
      if (url.includes("/get-session")) {
        return new Response(JSON.stringify(sessionBody("opaque-session")), {
          status: 200,
          headers: { "content-type": "application/json", "set-auth-jwt": "header.jwt.value" },
        });
      }
      if (url.includes("/sign-out")) return new Response("null", { status: 200 });
      return new Response(JSON.stringify({ message: "Unauthorized" }), { status: 401 });
    });

    await expect(restoreNeonToken("?neon_auth_session_verifier=abc")).resolves.toBe("header.jwt.value");
    const sessionCall = calls.find((call) => call.url.includes("/get-session"));
    expect(sessionCall?.url).toContain("neon_auth_session_verifier=abc");
    expect(sessionCall?.credentials).toBe("include");
    expect(calls.some((call) => call.url.includes("/token"))).toBe(false);
  });

  it("relit le vérificateur rangé dans next", async () => {
    installFetch((url) => {
      if (url.includes("/get-session")) {
        return new Response(JSON.stringify(sessionBody("opaque-session")), {
          status: 200,
          headers: { "content-type": "application/json", "set-auth-jwt": "nested.jwt.value" },
        });
      }
      return new Response("null", { status: 200 });
    });
    const next = encodeURIComponent("/?neon_auth_session_verifier=depuis-next");
    await expect(restoreNeonToken(`next=${next}`)).resolves.toBe("nested.jwt.value");
    expect(calls.find((call) => call.url.includes("/get-session"))?.url).toContain(
      "neon_auth_session_verifier=depuis-next",
    );
  });

  it("préfère set-auth-jwt à un session.token déjà en trois parties", async () => {
    installFetch((url) => {
      if (url.includes("/get-session")) {
        return new Response(JSON.stringify(sessionBody("eyJhbGciOiJIUzI1NiJ9.session.token")), {
          status: 200,
          headers: { "content-type": "application/json", "set-auth-jwt": "header.jwt.value" },
        });
      }
      if (url.endsWith("/token")) {
        return new Response(JSON.stringify({ token: "endpoint.jwt.value" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response("null", { status: 200 });
    });
    await expect(restoreNeonToken()).resolves.toBe("header.jwt.value");
    expect(calls.some((call) => call.url.endsWith("/token"))).toBe(false);
  });

  it("ignore un session.token à trois segments sans set-auth-jwt", async () => {
    installFetch((url) => {
      if (url.includes("/get-session")) {
        return new Response(JSON.stringify(sessionBody("eyJhbGciOiJIUzI1NiJ9.session.token")), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.endsWith("/token")) {
        return new Response(JSON.stringify({ token: "api.jwt.value" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response("null", { status: 200 });
    });
    await expect(restoreNeonToken()).resolves.toBe("api.jwt.value");
  });

  it("demande /token si la session n’a pas de JWT", async () => {
    installFetch((url) => {
      if (url.includes("/get-session")) {
        return new Response(JSON.stringify(sessionBody("opaque-session")), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.endsWith("/token")) {
        return new Response(JSON.stringify({ token: "endpoint.jwt.value" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response("null", { status: 200 });
    });
    await expect(restoreNeonToken()).resolves.toBe("endpoint.jwt.value");
    const tokenCall = calls.find((call) => call.url.endsWith("/token"));
    expect(tokenCall?.credentials).toBe("include");
  });

  it("garde le mot de passe sur le jeton dédié", async () => {
    installFetch((url) => {
      if (url.includes("/sign-in/email")) {
        return new Response(JSON.stringify({
          redirect: false,
          token: "opaque-session",
          user: user(),
        }), { status: 200, headers: { "content-type": "application/json" } });
      }
      if (url.includes("/token")) {
        return new Response(JSON.stringify({ token: "password.jwt.value" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response("null", { status: 200 });
    });
    await expect(signInWithPassword("ada@example.com", "mot-de-passe")).resolves.toBe("password.jwt.value");
  });
});
