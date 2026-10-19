import { useId, useMemo, useState } from "react"

import { Input } from "@/components/ui/input"
import type { TopicOut } from "@/lib/api"

const SHOWN = 40

// Auswahl eines Themas aus der Registry: Filterfeld und Liste. Schon vergebene Themen fehlen.
// Die Liste zeigt höchstens 40 Treffer, damit sie bei 195 Themen übersichtlich bleibt.
export function TopicPicker({
  topics,
  excluded,
  value,
  onChange,
  label,
}: {
  topics: TopicOut[]
  /** Themen, die nicht wählbar sind (am Geschäft schon aktiv). */
  excluded: string[]
  value: string
  onChange: (tagId: string) => void
  label: string
}) {
  const [query, setQuery] = useState("")
  const id = useId()
  const options = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return topics
      .filter((topic) => !excluded.includes(topic.tag_id))
      .filter((topic) => topic.name_de.toLowerCase().includes(needle))
  }, [topics, excluded, query])

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={`${id}-q`} className="text-muted-foreground">
        {label}
      </label>
      <Input
        id={`${id}-q`}
        value={query}
        placeholder="Thema suchen"
        onChange={(event) => setQuery(event.target.value)}
      />
      <select
        aria-label={`${label}: Treffer`}
        size={Math.min(6, Math.max(2, options.length))}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-input bg-background px-1 py-1 text-sm text-foreground"
      >
        {options.slice(0, SHOWN).map((topic) => (
          <option key={topic.tag_id} value={topic.tag_id}>
            {topic.name_de}
            {topic.scheme === "adhoc" ? " (Ad-hoc)" : ""}
          </option>
        ))}
      </select>
      {options.length === 0 && (
        <p className="text-muted-foreground">Kein Thema gefunden.</p>
      )}
      {options.length > SHOWN && (
        <p className="text-muted-foreground">
          {options.length - SHOWN} weitere: Suchbegriff eingrenzen.
        </p>
      )}
    </div>
  )
}
