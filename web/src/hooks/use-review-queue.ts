import { createContext, useContext } from "react"

import type { ReviewSummary } from "@/lib/api"

export interface ReviewQueueState {
  /** Zähler: offen, erledigt, je Bereich, Parlament und Thema; null, bis die API antwortet. */
  summary: ReviewSummary | null
  /** Schwelle der Klassifikation; null, solange die API noch nicht geantwortet hat. */
  threshold: number | null
  loading: boolean
  error: string | undefined
  /** Zählt die Neuladungen; Listen der Warteschlange laden neu, wenn er sich ändert. */
  version: number
  /** Lädt die Zähler und die Listen neu, z. B. nach einem Entscheid. */
  reload: () => void
}

export const ReviewQueueContext = createContext<ReviewQueueState | null>(null)

export function useReviewQueue(): ReviewQueueState {
  const state = useContext(ReviewQueueContext)
  if (state === null) {
    throw new Error("useReviewQueue braucht einen ReviewQueueProvider")
  }
  return state
}
