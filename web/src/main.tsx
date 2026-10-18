import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router"

import "./index.css"
import App from "./App.tsx"
import { ReviewProvider } from "@/components/review-provider.tsx"
import { ThemeProvider } from "@/components/theme-provider.tsx"

// Vergleich der Tabellen-Varianten: ?tabelle=tint oder ?tabelle=lines
const tableVariant = new URLSearchParams(window.location.search).get("tabelle")
if (tableVariant === "tint" || tableVariant === "lines") {
  document.documentElement.dataset.table = tableVariant
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider defaultTheme="light">
      <ReviewProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ReviewProvider>
    </ThemeProvider>
  </StrictMode>
)
