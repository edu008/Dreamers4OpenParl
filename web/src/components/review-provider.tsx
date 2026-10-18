import { useCallback, useMemo, useState, type ReactNode } from "react"

import { ReviewContext, type ReviewState } from "@/hooks/use-review"
import {
  loadDecisions,
  loadSession,
  saveDecisions,
  saveSession,
  type ReviewDecision,
  type ReviewMap,
  type ReviewSession,
} from "@/lib/review"

export function ReviewProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<ReviewSession | null>(() =>
    loadSession()
  )
  const [decisions, setDecisions] = useState<ReviewMap>(() => loadDecisions())

  const activate = useCallback((name: string, token: string) => {
    const next = { name: name.trim(), token: token.trim() }
    saveSession(next)
    setSession(next)
  }, [])

  const deactivate = useCallback(() => {
    saveSession(null)
    setSession(null)
  }, [])

  const decide = useCallback(
    (key: string, decision: ReviewDecision) => {
      if (session === null) return
      setDecisions((current) => {
        const next = {
          ...current,
          [key]: { decision, by: session.name, at: new Date().toISOString() },
        }
        saveDecisions(next)
        return next
      })
    },
    [session]
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
      active: session !== null,
      name: session?.name ?? "",
      decisions,
      activate,
      deactivate,
      decide,
      undo,
    }),
    [session, decisions, activate, deactivate, decide, undo]
  )
  return (
    <ReviewContext.Provider value={value}>{children}</ReviewContext.Provider>
  )
}
