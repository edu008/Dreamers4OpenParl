import { reviewReasons } from "@/lib/label-state"
import { reviewKey, type ReviewEntry, type ReviewMap } from "@/lib/review"
import {
  SAMPLE_AFFAIRS,
  type AffairLabel,
  type AffairRecord,
} from "@/lib/sample-affairs"

export interface QueueRow {
  affair: AffairRecord
  label: AffairLabel
  reasons: string[]
  entry: ReviewEntry | undefined
}

/**
 * Labels mit Prüfbedarf, die unsichersten zuerst. Entschiedene Labels bleiben in der Liste und
 * rücken ans Ende, damit man sieht, was schon erledigt ist.
 */
export function buildQueue(decisions: ReviewMap): QueueRow[] {
  return SAMPLE_AFFAIRS.flatMap((affair) =>
    affair.labels.map((label) => ({
      affair,
      label,
      reasons: reviewReasons(affair, label),
      entry: decisions[reviewKey(affair.id, label.tagId)],
    }))
  )
    .filter((row) => row.reasons.length > 0 || row.entry)
    .sort(
      (a, b) =>
        Number(Boolean(a.entry)) - Number(Boolean(b.entry)) ||
        a.label.confidence - b.label.confidence
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
  return openRows(rows).find((row) => row.affair.id !== currentAffairId)
}
