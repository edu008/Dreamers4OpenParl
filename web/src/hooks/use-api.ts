import { useEffect, useState } from "react"

import { fetchJson } from "@/lib/api"

interface Result<T> {
  path: string
  data?: T
  error?: string
}

/** Lädt JSON von der eigenen API; ein Pfadwechsel bricht die alte Anfrage ab. */
export function useApi<T>(path: string) {
  const [result, setResult] = useState<Result<T> | null>(null)
  const [last, setLast] = useState<T>()

  useEffect(() => {
    const controller = new AbortController()
    fetchJson<T>(path, controller.signal).then(
      (data) => {
        setResult({ path, data })
        setLast(data)
      },
      (error: unknown) => {
        if (!controller.signal.aborted) {
          const message = error instanceof Error ? error.message : String(error)
          setResult({ path, error: message })
        }
      }
    )
    return () => controller.abort()
  }, [path])

  const current = result?.path === path ? result : null
  return {
    data: current?.data,
    error: current?.error,
    loading: current === null,
    /** Zuletzt geladene Daten, auch von einem früheren Pfad: zum Stehenlassen beim Filtern. */
    last,
  }
}
