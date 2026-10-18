// Hilfen für den Seitenbaum aus GET /v1/pages (PRD 7.9). Die API liefert die Seiten sortiert.
import type { PageKind, WikiPage } from "@/lib/api"

export const HEART_ID = "heart"

export const KIND_LABEL: Record<PageKind, string> = {
  heart: "Heart",
  bereich: "Bereich",
  kapitel: "Kapitel",
  tag: "Tag-Seite",
  querschnitt: "Querschnitt",
}

export function pageHref(page: WikiPage): string {
  return page.kind === "heart" ? "/" : `/tags/${page.page_id}`
}

export function childrenOf(pages: WikiPage[], pageId: string): WikiPage[] {
  return pages.filter((page) => page.parent_id === pageId)
}

/** Querschnittsseiten, die eine Kapitel- oder Tag-Seite verlinkt (ohne sie zusammenzufassen). */
export function linkedQuerschnitt(
  pages: WikiPage[],
  pageId: string
): WikiPage[] {
  return pages.filter((page) => page.linked_from.includes(pageId))
}

/** Vorfahren von Heart bis zur Eltern-Seite. */
export function ancestorsOf(pages: WikiPage[], pageId: string): WikiPage[] {
  const byId = new Map(pages.map((page) => [page.page_id, page]))
  const chain: WikiPage[] = []
  const seen = new Set<string>()
  let current = byId.get(pageId)?.parent_id ?? null
  while (current !== null && !seen.has(current)) {
    seen.add(current)
    const page = byId.get(current)
    if (page === undefined) {
      break
    }
    chain.unshift(page)
    current = page.parent_id
  }
  return chain
}
