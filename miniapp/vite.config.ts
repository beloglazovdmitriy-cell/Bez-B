import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// host: true — чтобы открывать прототип с телефона в одной сети при отладке
// proxy /api → локальный FastAPI (api.py), чтобы не упираться в CORS в dev
export default defineConfig({
  // относительные пути к ассетам — чтобы работало на GitHub Pages
  // независимо от имени репозитория (project pages в подпапке).
  base: "./",
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
