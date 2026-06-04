import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Project site at https://hawarnekar.github.io/jars/ — assets and the data file are served
// under the /jars/ base path. Use import.meta.env.BASE_URL in code to build runtime URLs.
export default defineConfig({
  base: "/jars/",
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
