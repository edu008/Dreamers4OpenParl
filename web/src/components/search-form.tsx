import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useQuery } from "@/hooks/use-query"

// Das eine Suchfeld der öffentlichen Seite, mit einem Knopf (Hick's Law). «Suchen» setzt q in
// der Adresse und behält die Filter; leer abgeschickt zeigt die Seite wieder die neuesten
// Geschäfte. Was die Suche aus der Eingabe gemacht hat, steht über der Liste.
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
    // «Nur … suchen» gilt für eine Eingabe; eine neue sucht wieder mit Themenerkennung.
    next.delete("wortlaut")
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
        aria-label="Stichwort, Thema oder Frage"
        placeholder="Stichwort, Thema oder Frage"
        // GET /v1/search nimmt q bis 200 Zeichen (valid() in home.tsx).
        maxLength={200}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        className="h-14 flex-1 border-2 px-4 text-lg md:text-lg"
      />
      <Button type="submit" size="lg" className="h-14 px-10 text-base">
        Suchen
      </Button>
    </form>
  )
}
