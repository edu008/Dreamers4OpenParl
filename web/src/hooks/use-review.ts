import { createContext, useContext } from "react"

import type { ReviewDecision, ReviewMap, Role } from "@/lib/review"

export interface ReviewState {
  /** Gewählte Ansicht. Im MVP eine Darstellung, keine Zugangskontrolle. */
  role: Role
  /** Reviewer und Admin dürfen Labels entscheiden. */
  active: boolean
  isAdmin: boolean
  name: string
  decisions: ReviewMap
  setRole: (role: Role) => void
  setName: (name: string) => void
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
