import { useEffect, useState } from "react"

import { fetchJson, type TopicAffair, type TopicAffairs } from "@/lib/api"

const PAGE = 500
/** Mehr als das lädt die Oberfläche nicht auf einmal; der Rest steht in der API. */
export const MAX_AFFAIRS = 2000

export interface AllAffairs {
  items: TopicAffair[]
  /** Zahl aller Geschäfte der Seite laut API (kann grösser sein als `items`). */
  total: number
  loading: boolean
  error: string | undefined
}

// Lädt die Geschäfte einer Seite seitenweise (500 je Anfrage), bis alle da sind oder die Grenze
// erreicht ist. Die Auswertung (Kennzahlen, Verteilung, Export) rechnet dann im Browser.
export function useAllAffairs(pageId: string): AllAffairs {
  const [state, setState] = useState<AllAffairs>({
    items: [],
    total: 0,
    loading: true,
    error: undefined,
  })

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      const items: TopicAffair[] = []
      let total = 0
      while (items.length < MAX_AFFAIRS) {
        const page = await fetchJson<TopicAffairs>(
          `/v1/pages/${encodeURIComponent(pageId)}/affairs?limit=${PAGE}&offset=${items.length}`,
          controller.signal
        )
        total = page.total
        items.push(...page.items)
        if (items.length >= total || page.items.length === 0) break
      }
      return { items, total }
    }
    load().then(
      ({ items, total }) =>
        setState({ items, total, loading: false, error: undefined }),
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setState({
            items: [],
            total: 0,
            loading: false,
            error: error instanceof Error ? error.message : String(error),
          })
        }
      }
    )
    return () => controller.abort()
  }, [pageId])

  return state
}
