import { Link, useSearchParams } from "react-router"

import { SearchForm } from "@/components/search-form"

// Platzhalter: Die Suche übernimmt ein Agent im Backend (PRD 7.8). Sobald er angeschlossen ist,
// zeigt diese Seite seine Treffer (Form siehe lib/search-contract.ts).
export function SearchPage() {
  const [params] = useSearchParams()
  const query = params.get("q")?.trim() ?? ""
  return (
    <>
      <div className="flex flex-col gap-3">
        <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
          Suche
        </h1>
        <SearchForm key={query} initial={query} />
      </div>
      <section aria-live="polite" className="flex max-w-[68ch] flex-col gap-2">
        {query && (
          <p>
            Deine Suche: <strong className="font-semibold">«{query}»</strong>
          </p>
        )}
        <p className="text-muted-foreground">
          Die Suche in eigenen Worten ist noch nicht angeschlossen. Sie wird von
          einem Agenten im Backend ausgeführt und zeigt dann die Geschäfte mit
          Themen, Belegstelle und Verknüpfungen.
        </p>
        <p className="text-muted-foreground">
          Bis dahin kannst du in der{" "}
          <Link to="/" className="underline underline-offset-2">
            Themenübersicht
          </Link>{" "}
          stöbern.
        </p>
      </section>
    </>
  )
}
