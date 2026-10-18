import { useCallback, useMemo, useState, type ReactNode } from "react"

import { ReviewContext, type ReviewState } from "@/hooks/use-review"
import {
  loadDecisions,
  loadName,
  loadRole,
  saveDecisions,
  saveName,
  saveRole,
  type ReviewDecision,
  type ReviewMap,
  type Role,
} from "@/lib/review"

const DEFAULT_NAME = "Reviewer"

export function ReviewProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role>(() => loadRole())
  const [name, setNameState] = useState(() => loadName())
  const [decisions, setDecisions] = useState<ReviewMap>(() => loadDecisions())

  const setRole = useCallback((next: Role) => {
    saveRole(next)
    setRoleState(next)
  }, [])

  const setName = useCallback((next: string) => {
    saveName(next)
    setNameState(next)
  }, [])

  const decide = useCallback(
    (key: string, decision: ReviewDecision) => {
      if (role === "leser") return
      setDecisions((current) => {
        const next = {
          ...current,
          [key]: {
            decision,
            by: name.trim() || DEFAULT_NAME,
            at: new Date().toISOString(),
          },
        }
        saveDecisions(next)
        return next
      })
    },
    [role, name]
  )

  const undo = useCallback((key: string) => {
    setDecisions((current) => {
      const next = { ...current }
      delete next[key]
      saveDecisions(next)
      return next
    })
  }, [])

  const value = useMemo<ReviewState>(
    () => ({
      role,
      active: role !== "leser",
      isAdmin: role === "admin",
      name,
      decisions,
      setRole,
      setName,
      decide,
      undo,
    }),
    [role, name, decisions, setRole, setName, decide, undo]
  )
  return (
    <ReviewContext.Provider value={value}>{children}</ReviewContext.Provider>
  )
}
