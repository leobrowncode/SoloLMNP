import react from "@vitejs/plugin-react";
import type { ProxyOptions } from "vite";
import { defineConfig } from "vitest/config";

// The API accepts a write only when Origin matches the request base URL.
// Nginx already forwards the browser Host. The dev proxy must do the same,
// otherwise every local write is rejected as a foreign origin.
function apiProxy(): ProxyOptions {
  return {
    target: "http://127.0.0.1:8000",
    changeOrigin: false,
    configure(proxy) {
      proxy.on("proxyReq", (proxyReq, incoming) => {
        const host = incoming.headers.host;
        if (typeof host === "string") proxyReq.setHeader("host", host);
      });
    },
  };
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1", port: 5173, strictPort: true,
    proxy: { "/api": apiProxy() },
  },
  preview: {
    host: "127.0.0.1", port: 4173, strictPort: true,
    proxy: { "/api": apiProxy() },
  },
  test: {
    environment: "jsdom", setupFiles: ["./src/test/setup.ts"],
    clearMocks: true, restoreMocks: true,
  },
});
