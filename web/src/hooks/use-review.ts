import { createContext, useContext } from "react"

import type { AffairTopics, ReviewAction } from "@/lib/api"
import type { Role } from "@/lib/review"

export interface ReviewState {
  /** Ansicht aus der Adresse: «admin» unter /admin. Im MVP keine Zugangskontrolle. */
  role: Role
  /** Admin darf Labels entscheiden. */
  active: boolean
  isAdmin: boolean
  name: string
  setName: (name: string) => void
  /** Speichert den Entscheid im Backend und gibt das Geschäft mit den neuen Labels zurück. */
  decide: (
    affairId: string,
    tagId: string,
    action: Extract<ReviewAction, "confirm" | "reject" | "undo">
  ) => Promise<AffairTopics>
}

export const ReviewContext = createContext<ReviewState | null>(null)

export function useReview(): ReviewState {
  const state = useContext(ReviewContext)
  if (state === null) {
    throw new Error("useReview braucht einen ReviewProvider")
  }
  return state
}
