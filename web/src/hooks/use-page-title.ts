import { useEffect } from "react"

/** Setzt den Tab-Titel der Seite. Ohne Titel (z. B. beim Laden) bleibt der bisherige stehen. */
export function usePageTitle(title: string | undefined) {
  useEffect(() => {
    if (title) document.title = `${title} · ParlTopics`
  }, [title])
}
