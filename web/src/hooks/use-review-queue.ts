import { createContext, useContext } from "react"

import type { ReviewCandidate } from "@/lib/review-queue"

export interface ReviewQueueState {
  candidates: ReviewCandidate[]
  loading: boolean
  error: string | undefined
}

export const ReviewQueueContext = createContext<ReviewQueueState | null>(null)

export function useReviewQueue(): ReviewQueueState {
  const state = useContext(ReviewQueueContext)
  if (state === null) {
    throw new Error("useReviewQueue braucht einen ReviewQueueProvider")
  }
  return state
}
