import {
  fetchJson,
  type LabelOut,
  type ReviewItem,
  type ReviewQueue,
  type ReviewReason,
} from "@/lib/api"

/** Ein Label aus der Warteschlange der Sidecar-API (offen oder entschieden). */
export interface ReviewCandidate {
  affairId: string
  number: string | null
  title: string
  body: string | null
  bodyKey: string
  bodyLevel: string | null
  tagId: string
  labelName: string
  confidence: number
  evidence: string | null
  evidenceVerified: boolean
  reasons: ReviewReason[]
  /** Entscheid des Labels; nur bei erledigten gesetzt. Name und Zeit stammen vom Backend. */
  decision: LabelOut["review_status"]
  decidedBy: string | null
  decidedAt: string | null
}

export function toCandidate(item: ReviewItem): ReviewCandidate {
  return {
    affairId: String(item.affair_id),
    number: item.number,
    title: item.title ?? `Geschäft ${item.affair_id}`,
    body: item.body_name,
    bodyKey: item.body_key,
    bodyLevel: item.body_level,
    tagId: item.label.tag_id,
    labelName: item.label.name_de,
    confidence: item.label.confidence,
    evidence: item.label.evidence,
    evidenceVerified: item.label.evidence_verified,
    reasons: item.reasons,
    decision: item.label.review_status,
    decidedBy: item.label.reviewed_by,
    decidedAt: item.label.reviewed_at,
  }
}

const PAGE = 500
// Obergrenze der Seiten je Zustand, damit eine fehlerhafte Antwort nicht endlos weiterlädt.
const MAX_PAGES = 20

/** Alle Labels eines Zustands, auf dem Server gefiltert (`query`: reason, page_id, body_key). */
export async function loadQueue(
  state: "open" | "done",
  query: string,
  signal: AbortSignal
): Promise<ReviewCandidate[]> {
  const rows: ReviewCandidate[] = []
  for (let page = 0; page < MAX_PAGES; page++) {
    const params = new URLSearchParams(query)
    params.set("state", state)
    params.set("limit", String(PAGE))
    params.set("offset", String(page * PAGE))
    const queue = await fetchJson<ReviewQueue>(
      `/v1/reviews/queue?${params}`,
      signal
    )
    rows.push(...queue.items.map(toCandidate))
    if (queue.items.length === 0 || rows.length >= queue.total) break
  }
  return rows
}
