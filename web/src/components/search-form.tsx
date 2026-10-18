import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useQuery } from "@/hooks/use-query"

// Das eine Suchfeld der öffentlichen Seite. Setzt q in der Adresse und behält die Filter; leer
// abgeschickt zeigt die Seite wieder die neuesten Geschäfte.
export function SearchForm({ initial = "" }: { initial?: string }) {
  const [params, setParams] = useQuery()
  const [query, setQuery] = useState(initial)

  function submit(event: FormEvent) {
    event.preventDefault()
    const next = new URLSearchParams(params)
    const text = query.trim()
    if (text) next.set("q", text)
    else next.delete("q")
    next.delete("seite")
    setParams(next)
  }

  return (
    <form
      role="search"
      onSubmit={submit}
      className="flex w-full max-w-3xl flex-col gap-3 sm:flex-row"
    >
      <Input
        type="search"
        aria-label="Geschäfte suchen"
        placeholder="Stichwort, zum Beispiel Velowege oder Datenschutz"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        className="h-14 flex-1 px-6 text-lg"
      />
      <Button type="submit" size="lg" className="h-14 px-8 text-base">
        Suchen
      </Button>
    </form>
  )
}
