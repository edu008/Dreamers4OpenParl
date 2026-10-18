import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// Entwicklung: `npm run dev` (Port 5173) leitet API-Aufrufe an FastAPI auf 127.0.0.1:8000 weiter.
// Build: `npm run build` schreibt web/dist; FastAPI liefert es aus (ADR 0006).
const API = "http://127.0.0.1:8000"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    proxy: { "/v1": API, "/healthz": API },
  },
})
