import type { LabelOut, ReviewItem, ReviewReason } from "@/lib/api"

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
  /** Bereich des Themas (Seitenbaum), für den Filter. */
  areaId: string | null
  areaName: string | null
  reasons: ReviewReason[]
  /** Entscheid des Labels; nur bei erledigten gesetzt. Name und Zeit stammen vom Backend. */
  decision: LabelOut["review_status"]
  decidedBy: string | null
  decidedAt: string | null
}

export function toCandidate(
  item: ReviewItem,
  area: { id: string; name: string } | null
): ReviewCandidate {
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
    areaId: area?.id ?? null,
    areaName: area?.name ?? null,
    reasons: item.reasons,
    decision: item.label.review_status,
    decidedBy: item.label.reviewed_by,
    decidedAt: item.label.reviewed_at,
  }
}

/** Nächstes offenes Label in einem anderen Geschäft als dem gerade geöffneten. */
export function nextOpen(
  open: ReviewCandidate[],
  currentAffairId: string
): ReviewCandidate | undefined {
  return open.find((row) => row.affairId !== currentAffairId)
}
