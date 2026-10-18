import { createContext, useContext } from "react"

import type { ReviewDecision, ReviewMap } from "@/lib/review"

export interface ReviewState {
  active: boolean
  name: string
  decisions: ReviewMap
  activate: (name: string, token: string) => void
  deactivate: () => void
  decide: (key: string, decision: ReviewDecision) => void
  undo: (key: string) => void
}

export const ReviewContext = createContext<ReviewState | null>(null)

export function useReview(): ReviewState {
  const state = useContext(ReviewContext)
  if (state === null) {
    throw new Error("useReview braucht einen ReviewProvider")
  }
  return state
}
