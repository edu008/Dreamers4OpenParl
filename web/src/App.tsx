import { Route, Routes } from "react-router"

import { Layout } from "@/components/layout"
import { HomePage } from "@/pages/home"
import { AffairPage } from "@/pages/affair"
import { StatusPage } from "@/pages/status"
import { ReviewPage } from "@/pages/review"
import {
  GraphPage,
  NotFoundPage,
  SearchPage,
} from "@/pages/placeholders"
import { TagPage } from "@/pages/tag-page"

// Routen der Web-App (PRD 7.5). FastAPI liefert für alle Pfade ausserhalb von /v1 index.html aus.
export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="tags/:tagId" element={<TagPage />} />
        <Route path="geschaefte/:affairId" element={<AffairPage />} />
        <Route path="suche" element={<SearchPage />} />
        <Route path="review" element={<ReviewPage />} />
        <Route path="graph" element={<GraphPage />} />
        <Route path="status" element={<StatusPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App
