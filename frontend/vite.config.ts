import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    // edge-e2e Caddy proxies with Host: edge-e2e during Playwright runs.
    allowedHosts: ["edge-e2e", "localhost", "frontend-dev"],
    watch: {
      // Required for reliable HMR on Windows bind mounts.
      usePolling: true,
    },
  },

  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
  },
});
