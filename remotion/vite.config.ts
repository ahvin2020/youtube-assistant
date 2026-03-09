import { defineConfig } from "vite";

export default defineConfig({
  root: "src/editor",
  server: {
    port: 3100,
  },
  resolve: {
    alias: {
      "@": "/src",
    },
  },
});
