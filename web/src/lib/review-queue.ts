import { reviewKey, type ReviewEntry, type ReviewMap } from "@/lib/review"

/** Ein Label mit Prüfbedarf, wie es die Sidecar-API liefert. */
export interface ReviewCandidate {
  affairId: string
  number: string | null
  title: string
  body: string | null
  tagId: string
  labelName: string
  confidence: number
  evidence: string | null
  evidenceVerified: boolean
  /** Bereich des Themas (Seitenbaum), für den Filter. */
  areaId: string | null
  areaName: string | null
  reasons: string[]
}

export interface QueueRow extends ReviewCandidate {
  entry: ReviewEntry | undefined
}

/**
 * Kandidaten mit den lokalen Entscheiden. Entschiedene Labels bleiben in der Liste und rücken
 * ans Ende; die Reihenfolge ist sonst nach Konfidenz aufsteigend.
 */
export function buildQueue(
  candidates: ReviewCandidate[],
  decisions: ReviewMap
): QueueRow[] {
  return candidates
    .map((candidate) => ({
      ...candidate,
      entry: decisions[reviewKey(candidate.affairId, candidate.tagId)],
    }))
    .sort(
      (a, b) =>
        Number(Boolean(a.entry)) - Number(Boolean(b.entry)) ||
        a.confidence - b.confidence
    )
}

export function openRows(rows: QueueRow[]): QueueRow[] {
  return rows.filter((row) => !row.entry)
}

/** Nächstes offenes Label in einem anderen Geschäft als dem gerade geöffneten. */
export function nextOpenRow(
  rows: QueueRow[],
  currentAffairId: string
): QueueRow | undefined {
  return openRows(rows).find((row) => row.affairId !== currentAffairId)
}
