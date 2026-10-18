import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router"

import "./index.css"
import App from "./App.tsx"
import { ReviewProvider } from "@/components/review-provider.tsx"
import { ThemeProvider } from "@/components/theme-provider.tsx"

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
