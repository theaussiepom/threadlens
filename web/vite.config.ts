import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// ThreadLens Core serves the built dashboard from its static directory.
//
// `base: "./"` emits relative asset URLs so the dashboard works unchanged when
// hosted at `/`, behind a reverse proxy subpath, or under a Home Assistant
// Ingress prefix (e.g. `/api/hassio_ingress/<token>/`). Output goes into the
// repo `static/` directory consumed by `THREADLENS_STATIC_DIR`.
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    outDir: "../static",
    emptyOutDir: true,
    sourcemap: false,
  },
});
