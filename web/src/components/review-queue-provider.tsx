import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"

import {
  ReviewQueueContext,
  type ReviewQueueState,
} from "@/hooks/use-review-queue"
import { fetchJson, type PageTree, type ReviewQueue } from "@/lib/api"
import { ancestorsOf } from "@/lib/tree"
import { toCandidate, type ReviewCandidate } from "@/lib/review-queue"

const PAGE = 500
// Obergrenze der Seiten je Zustand, damit eine fehlerhafte Antwort nicht endlos weiterlädt.
const MAX_PAGES = 20

type AreaOf = (tagId: string) => { id: string; name: string } | null

/** Bereich eines Themas aus dem Seitenbaum, für den Filter in der Review-Liste. */
function areaLookup(tree: PageTree): AreaOf {
  return (tagId) => {
    const self = tree.pages.find((page) => page.page_id === tagId)
    const chain = [...ancestorsOf(tree.pages, tagId), ...(self ? [self] : [])]
    const area = chain.find((page) => page.kind === "bereich")
    return area ? { id: area.page_id, name: area.title } : null
  }
}

async function loadState(
  state: "open" | "done",
  areaOf: AreaOf,
  signal: AbortSignal
): Promise<{ threshold: number; rows: ReviewCandidate[] }> {
  const rows: ReviewCandidate[] = []
  let threshold = 0
  for (let page = 0; page < MAX_PAGES; page++) {
    const queue = await fetchJson<ReviewQueue>(
      `/v1/reviews/queue?state=${state}&limit=${PAGE}&offset=${page * PAGE}`,
      signal
    )
    threshold = queue.threshold
    rows.push(
      ...queue.items.map((item) => toCandidate(item, areaOf(item.label.tag_id)))
    )
    if (queue.items.length === 0 || rows.length >= queue.total) break
  }
  return { threshold, rows }
}

interface Loaded {
  open: ReviewCandidate[]
  done: ReviewCandidate[]
  threshold: number | null
  error: string | undefined
}

export function ReviewQueueProvider({ children }: { children: ReactNode }) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [version, setVersion] = useState(0)
  const reload = useCallback(() => setVersion((current) => current + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    fetchJson<PageTree>("/v1/pages", controller.signal)
      .then((tree) => {
        const areaOf = areaLookup(tree)
        return Promise.all([
          loadState("open", areaOf, controller.signal),
          loadState("done", areaOf, controller.signal),
        ])
      })
      .then(
      ([open, done]) =>
        setLoaded({
          open: open.rows,
          done: done.rows,
          threshold: open.threshold,
          error: undefined,
        }),
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setLoaded({
            open: [],
            done: [],
            threshold: null,
            error: error instanceof Error ? error.message : String(error),
          })
        }
      }
    )
    return () => controller.abort()
  }, [version])

  // Beim Neuladen bleibt die alte Liste stehen, bis die neue da ist.
  const value = useMemo<ReviewQueueState>(
    () => ({
      open: loaded?.open ?? [],
      done: loaded?.done ?? [],
      threshold: loaded?.threshold ?? null,
      loading: loaded === null,
      error: loaded?.error,
      reload,
    }),
    [loaded, reload]
  )

  return (
    <ReviewQueueContext.Provider value={value}>
      {children}
    </ReviewQueueContext.Provider>
  )
}
