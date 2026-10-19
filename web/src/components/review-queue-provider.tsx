import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { useLocation } from "react-router"

import {
  ReviewQueueContext,
  type ReviewQueueState,
} from "@/hooks/use-review-queue"
import { fetchJson, type ReviewSummary } from "@/lib/api"
import { isAdminPath } from "@/lib/review"

interface Loaded {
  summary: ReviewSummary | null
  error: string | undefined
}

// Zähler der Warteschlange aus GET /v1/reviews/summary: für den Admin-Kopf, die Filter der
// Review-Seite und die Schwelle der Klassifikation. Die Listen lädt die Review-Seite selbst.
export function ReviewQueueProvider({ children }: { children: ReactNode }) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [version, setVersion] = useState(0)
  const reload = useCallback(() => setVersion((current) => current + 1), [])
  // Nur der Admin-Bereich braucht die Zähler; öffentliche Seiten laden sie nicht.
  const admin = isAdminPath(useLocation().pathname)

  useEffect(() => {
    if (!admin) return
    const controller = new AbortController()
    fetchJson<ReviewSummary>("/v1/reviews/summary", controller.signal).then(
      (summary) => setLoaded({ summary, error: undefined }),
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setLoaded({
            summary: null,
            error: error instanceof Error ? error.message : String(error),
          })
        }
      }
    )
    return () => controller.abort()
  }, [version, admin])

  // Beim Neuladen bleiben die alten Zähler stehen, bis die neuen da sind.
  const value = useMemo<ReviewQueueState>(
    () => ({
      summary: loaded?.summary ?? null,
      threshold: loaded?.summary?.threshold ?? null,
      loading: loaded === null,
      error: loaded?.error,
      version,
      reload,
    }),
    [loaded, version, reload]
  )

  return (
    <ReviewQueueContext.Provider value={value}>
      {children}
    </ReviewQueueContext.Provider>
  )
}
