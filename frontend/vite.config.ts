// Vite config. The dev server proxies /api to the FastAPI backend on
// 127.0.0.1:8000; a production build is served by FastAPI itself.
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } },
  },
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 5000 },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
