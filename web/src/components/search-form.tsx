import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useQuery } from "@/hooks/use-query"

// Das eine Suchfeld der öffentlichen Seite. «Suchen» setzt q in der Adresse und behält die
// Filter; leer abgeschickt zeigt die Seite wieder die neuesten Geschäfte. «Frage stellen» gibt
// denselben Text als Frage an den Agenten (onAsk).
export function SearchForm({
  initial = "",
  onAsk,
  asking = false,
}: {
  initial?: string
  onAsk?: (question: string) => void
  asking?: boolean
}) {
  const [params, setParams] = useQuery()
  const [query, setQuery] = useState(initial)
  const [tooShort, setTooShort] = useState(false)

  function ask() {
    const text = query.trim()
    // Die API nimmt Fragen ab 3 Zeichen (NavigateIn).
    setTooShort(text.length < 3)
    if (text.length >= 3) onAsk?.(text)
  }

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
    <div className="flex w-full max-w-3xl flex-col gap-3">
      <form
        role="search"
        onSubmit={submit}
        className="flex flex-col gap-3 sm:flex-row"
      >
        <Input
          type="search"
          aria-label="Stichwort oder Frage"
          aria-describedby="ask-hint"
          placeholder="Stichwort oder Frage, zum Beispiel Velowege"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setTooShort(false)
          }}
          className="h-14 flex-1 border-2 px-4 text-lg md:text-lg"
        />
        <Button type="submit" size="lg" className="h-14 px-10 text-base">
          Suchen
        </Button>
      </form>
      {onAsk && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Button
            type="button"
            variant="outline"
            disabled={asking}
            onClick={ask}
          >
            {asking ? "Frage läuft …" : "Frage stellen"}
          </Button>
          <p id="ask-hint" className="text-sm text-muted-foreground">
            {tooShort
              ? "Bitte zuerst eine Frage ins Feld schreiben."
              : "In eigenen Worten fragen, die Antwort nennt ihre Quellen."}
          </p>
        </div>
      )}
    </div>
  )
}
