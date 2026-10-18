import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

// Suchfeld für die Startseite (gross) und die Kopfzeile (kompakt). Sendet zu /suche?q=…
export function SearchForm({
  initial = "",
  compact = false,
}: {
  initial?: string
  compact?: boolean
}) {
  const navigate = useNavigate()
  const [query, setQuery] = useState(initial)

  function submit(event: FormEvent) {
    event.preventDefault()
    const text = query.trim()
    if (text) navigate(`/suche?q=${encodeURIComponent(text)}`)
  }

  return (
    <form
      role="search"
      onSubmit={submit}
      className={compact ? "flex gap-2" : "flex max-w-2xl gap-2"}
    >
      <Input
        type="search"
        aria-label="Geschäfte suchen"
        placeholder={
          compact
            ? "Suchen"
            : "Zum Beispiel: Waffenexporte, Datenschutz, Berufsbildung"
        }
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        className={compact ? "h-8 w-44" : "h-10 text-base"}
      />
      <Button type="submit" size={compact ? "sm" : "lg"}>
        Suchen
      </Button>
    </form>
  )
}
