import react from "@vitejs/plugin-react";
import type { ProxyOptions } from "vite";
import { defineConfig } from "vitest/config";

// The browser calls Vite on the same origin. Drop the forwarded Origin so the
// API sees the documented local proxy, while Sec-Fetch-Site still blocks cross-site writes.
const localProxy: ProxyOptions["configure"] = (proxy) => {
  proxy.on("proxyReq", (proxyReq) => {
    proxyReq.removeHeader("origin");
  });
};

export default defineConfig({
  plugins: [react()],
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
