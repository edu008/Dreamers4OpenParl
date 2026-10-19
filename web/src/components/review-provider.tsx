import { useCallback, useMemo, useState, type ReactNode } from "react"
import { useLocation } from "react-router"

import { ReviewContext, type ReviewState } from "@/hooks/use-review"
import { useReviewQueue } from "@/hooks/use-review-queue"
import { postJson, type AffairTopics, type ReviewIn } from "@/lib/api"
import { isAdminPath, loadName, saveName, type Role } from "@/lib/review"

// Das Backend verlangt einen Namen; wer keinen eintippt, entscheidet als «Reviewer».
const DEFAULT_NAME = "Reviewer"

export function ReviewProvider({ children }: { children: ReactNode }) {
  // Die Ansicht folgt der Adresse: unter /admin wird entschieden, alles andere ist rein lesend.
  const role: Role = isAdminPath(useLocation().pathname) ? "admin" : "leser"
  const [name, setNameState] = useState(() => loadName())
  const { reload } = useReviewQueue()

  const setName = useCallback((next: string) => {
    saveName(next)
    setNameState(next)
  }, [])

  const decide = useCallback<ReviewState["decide"]>(
    async (affairId, tagId, action, newTagId) => {
      if (role === "leser")
        throw new Error("Die Ansicht «Leser» darf nicht entscheiden.")
      const body: ReviewIn = {
        affair_id: Number(affairId),
        tag_id: tagId,
        action,
        ...(newTagId ? { new_tag_id: newTagId } : {}),
        user_name: name.trim() || DEFAULT_NAME,
      }
      const affair = await postJson<AffairTopics>("/v1/reviews", body)
      reload()
      return affair
    },
    [role, name, reload]
  )

  const value = useMemo<ReviewState>(
    () => ({
      role,
      active: role !== "leser",
      isAdmin: role === "admin",
      name,
      setName,
      decide,
    }),
    [role, name, setName, decide]
  )
  return (
    <ReviewContext.Provider value={value}>{children}</ReviewContext.Provider>
  )
}
