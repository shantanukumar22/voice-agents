import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Voice bot (:7860) for WebRTC + TTS; platform API (:8000) for OCR / encounters / RAG
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api/encounters": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/api/verify-abha": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/api/scan-document": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/api/patients": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/api/rag": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      // Guide TTS lives on the voice bot (same Cartesia Kabir voice)
      "/api/tts": {
        target: "http://127.0.0.1:7860",
        changeOrigin: true,
      },
      "/api": {
        target: "http://127.0.0.1:7860",
        changeOrigin: true,
      },
      "/health": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
