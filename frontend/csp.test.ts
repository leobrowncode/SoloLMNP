import { describe, expect, it } from "vitest";
import { contentSecurityPolicy } from "./csp";

const AUTH = "https://ep-example.neonauth.c-3.eu-central-1.aws.neon.tech/neondb/auth";

describe("content security policy", () => {
  it("allows the Neon Auth origin and the Blob upload host", () => {
    const policy = contentSecurityPolicy(AUTH);
    expect(policy).toContain(
      "connect-src 'self' https://ep-example.neonauth.c-3.eu-central-1.aws.neon.tech https://vercel.com",
    );
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).not.toContain("/neondb/auth");
  });

  it("stays on this origin when Neon Auth is not configured", () => {
    expect(contentSecurityPolicy("")).toContain("connect-src 'self' https://vercel.com");
  });

  it("rejects a credential in the auth URL", () => {
    expect(() => contentSecurityPolicy("https://user:secret@auth.example/auth")).toThrow(/secret/);
  });
});
