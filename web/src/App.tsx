import { Route, Routes } from "react-router"

import { Layout } from "@/components/layout"
import { HomePage } from "@/pages/home"
import { AffairPage } from "@/pages/affair"
import { AdminPage } from "@/pages/admin"
import { ReviewPage } from "@/pages/review"
import { GraphPage } from "@/pages/graph"
import { NotFoundPage } from "@/pages/placeholders"
import { SearchPage } from "@/pages/search"
import { TagPage } from "@/pages/tag-page"

// Routen der Web-App (PRD 7.5). FastAPI liefert für alle Pfade ausserhalb von /v1 index.html aus.
// Öffentliche Seiten sind rein lesend; entscheiden kann man nur unter /review (Council 18.10.2026).
export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="tags/:tagId" element={<TagPage />} />
        <Route
          path="geschaefte/:affairId"
          element={<AffairPage mode="public" />}
        />
        <Route path="suche" element={<SearchPage />} />
        <Route path="review" element={<ReviewPage />} />
        <Route
          path="review/geschaefte/:affairId"
          element={<AffairPage mode="review" />}
        />
        <Route path="graph" element={<GraphPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App
