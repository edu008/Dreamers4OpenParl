import { useCallback, useMemo, useState, type ReactNode } from "react"

import { ReviewContext, type ReviewState } from "@/hooks/use-review"
import { useReviewQueue } from "@/hooks/use-review-queue"
import { postJson, type AffairTopics, type ReviewIn } from "@/lib/api"
import { loadName, loadRole, saveName, saveRole, type Role } from "@/lib/review"

// Das Backend verlangt einen Namen; wer keinen eintippt, entscheidet als «Reviewer».
const DEFAULT_NAME = "Reviewer"

export function ReviewProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role>(() => loadRole())
  const [name, setNameState] = useState(() => loadName())
  const { reload } = useReviewQueue()

  const setRole = useCallback((next: Role) => {
    saveRole(next)
    setRoleState(next)
  }, [])

  const setName = useCallback((next: string) => {
    saveName(next)
    setNameState(next)
  }, [])

  const decide = useCallback<ReviewState["decide"]>(
    async (affairId, tagId, action) => {
      if (role === "leser") throw new Error("Die Ansicht «Leser» darf nicht entscheiden.")
      const body: ReviewIn = {
        affair_id: Number(affairId),
        tag_id: tagId,
        action,
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
      setRole,
      setName,
      decide,
    }),
    [role, name, setRole, setName, decide]
  )
  return (
    <ReviewContext.Provider value={value}>{children}</ReviewContext.Provider>
  )
}
