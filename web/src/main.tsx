import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router"

import "./index.css"
import App from "./App.tsx"
import { ReviewProvider } from "@/components/review-provider.tsx"
import { ReviewQueueProvider } from "@/components/review-queue-provider.tsx"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ReviewProvider>
      <ReviewQueueProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ReviewQueueProvider>
    </ReviewProvider>
  </StrictMode>
)
