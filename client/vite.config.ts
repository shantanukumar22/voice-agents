import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Proxy /api → bot so the browser talks same-origin (no CORS).
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:7860",
        changeOrigin: true,
      },
      "/health": {
        target: "http://127.0.0.1:7860",
        changeOrigin: true,
      },
    },
  },
});
