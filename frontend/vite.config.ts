import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import type { Plugin, ProxyOptions } from "vite";
import { defineConfig } from "vitest/config";
import { contentSecurityPolicy } from "./csp.ts";

function contentSecurityPolicyPlugin(): Plugin {
  return {
    name: "sololmnp-csp",
    apply: "build",
    transformIndexHtml(html) {
      const policy = contentSecurityPolicy(process.env.VITE_NEON_AUTH_URL ?? "");
      const meta = `<meta http-equiv="Content-Security-Policy" content="${policy}">`;
      return html.replace("<head>", `<head>${meta}`);
    },
  };
}

// The browser calls Vite on the same origin. Drop the forwarded Origin so the
// API sees the documented local proxy, while Sec-Fetch-Site still blocks cross-site writes.
const localProxy: ProxyOptions["configure"] = (proxy) => {
  proxy.on("proxyReq", (proxyReq) => {
    proxyReq.removeHeader("origin");
  });
};

export default defineConfig({
  envDir: fileURLToPath(new URL("..", import.meta.url)),
  plugins: [react(), contentSecurityPolicyPlugin()],
  server: {
    host: "127.0.0.1", port: 5173, strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:8000", configure: localProxy } },
  },
  preview: {
    host: "127.0.0.1", port: 4173, strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:8000", configure: localProxy } },
  },
  test: {
    environment: "jsdom", setupFiles: ["./src/test/setup.ts"],
    clearMocks: true, restoreMocks: true,
  },
});
