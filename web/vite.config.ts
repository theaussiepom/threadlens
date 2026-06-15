import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// ThreadLens Core serves the built dashboard from its static directory.
//
// `base: "./"` emits relative asset URLs so the dashboard works unchanged when
// hosted at `/`, behind a reverse proxy subpath, or under a Home Assistant
// Ingress prefix. Output goes into the repo `static/` directory consumed by
// `THREADLENS_STATIC_DIR`.
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "../static",
    emptyOutDir: true,
    sourcemap: false,
  },
});
