import { Route, Routes } from "react-router"

import { Layout } from "@/components/layout"
import { HomePage } from "@/pages/home"
import { AffairPage } from "@/pages/affair"
import { AffairFactsPage } from "@/pages/affair-facts"
import { AdminPage } from "@/pages/admin"
import { AdhocNewPage } from "@/pages/adhoc-new"
import { QualityPage } from "@/pages/quality"
import { ReviewPage } from "@/pages/review"
import { GraphPage } from "@/pages/graph"
import { HelpPage } from "@/pages/help"
import { BodiesPage } from "@/pages/bodies"
import { NotFoundPage } from "@/pages/placeholders"
import { TopicsPage } from "@/pages/topics"
import { TagPage } from "@/pages/tag-page"

// Routen der Web-App (PRD 7.5). FastAPI liefert für alle Pfade ausserhalb von /v1 index.html aus.
// Zwei Bereiche: / ist öffentlich und hat nur die Suche über die Geschäfte; /admin ist für Review,
// Themen und Graph. Entscheiden kann man nur unter /admin/review (Council 18.10.2026).
export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="geschaefte/:affairId" element={<AffairFactsPage />} />
        <Route path="hilfe" element={<HelpPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="admin/thema-neu" element={<AdhocNewPage />} />
        <Route path="admin/qualitaet" element={<QualityPage />} />
        <Route path="admin/review" element={<ReviewPage />} />
        <Route
          path="admin/review/geschaefte/:affairId"
          element={<AffairPage mode="review" />}
        />
        <Route path="admin/themen" element={<TopicsPage />} />
        <Route path="admin/themen/:tagId" element={<TagPage />} />
        <Route path="admin/graph" element={<GraphPage />} />
        <Route path="admin/parlamente" element={<BodiesPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App
