import { createContext, useContext } from "react"

import type { ReviewCandidate } from "@/lib/review-queue"

export interface ReviewQueueState {
  /** Offene Labels, unsicherste zuerst. */
  open: ReviewCandidate[]
  /** Labels mit Entscheid, neuester zuerst. */
  done: ReviewCandidate[]
  /** Schwelle der Klassifikation; null, solange die API noch nicht geantwortet hat. */
  threshold: number | null
  loading: boolean
  error: string | undefined
  /** Lädt die Warteschlange neu, z. B. nach einem Entscheid. */
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
