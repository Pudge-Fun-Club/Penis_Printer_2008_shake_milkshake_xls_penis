/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendPort = process.env.PLOTTER_PORT ?? "8010";

// Build straight into the FastAPI static dir so the backend can serve the SPA.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../plotter/web/static",
    emptyOutDir: true,
  },
  test: {
    setupFiles: ["src/test/setup.ts"],
    // Node's experimental storage globals mask jsdom's browser storage.
    poolOptions: {
      forks: { execArgv: Number(process.versions.node.split(".")[0]) >= 22
        ? ["--no-experimental-webstorage"] : [] },
    },
  },
  server: {
    proxy: {
      "/api": {
        target: `http://localhost:${backendPort}`,
        ws: true,
      },
    },
  },
});
