import { Link, useLocation } from "react-router"

import { Confidence } from "@/components/confidence"
import { SearchForm } from "@/components/search-form"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import { usePageTitle } from "@/hooks/use-page-title"
import type { SearchHit, SearchResult } from "@/lib/api"
import { parseSnippet } from "@/lib/snippet"

const LIMIT = 20

function formatDate(iso: string | null): string {
  if (!iso) return ""
  const [year, month, day] = iso.split("-")
  return `${day}.${month}.${year}`
}

function Snippet({ headline }: { headline: string }) {
  return (
    <p className="max-w-[68ch] text-sm leading-relaxed text-muted-foreground">
      {parseSnippet(headline).map((part, index) =>
        part.marked ? (
          <mark key={index} className="bg-margin-tint font-medium text-foreground">
            {part.text}
          </mark>
        ) : (
          part.text
        )
      )}
    </p>
  )
}

function Hit({ hit }: { hit: SearchHit }) {
  const title = hit.title ?? `Geschäft ${hit.affair_id}`
  return (
    <li className="flex flex-col gap-1.5 border-b border-border py-4">
      <p className="tabular text-xs text-muted-foreground">
        {[
          hit.number,
          hit.type_de ?? hit.type,
          hit.body_name ?? hit.body_key,
          formatDate(hit.begin_date),
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <Link
        to={`/geschaefte/${hit.affair_id}`}
        className="text-base leading-snug font-medium underline-offset-4 hover:underline"
      >
        {title}
      </Link>
      {hit.headline && <Snippet headline={hit.headline} />}
      {hit.topics.length > 0 && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 pt-0.5 text-xs">
          {hit.topics.map((topic) => (
            <li key={topic.tag_id} className="flex items-center gap-1.5">
              <Link
                to={`/tags/${encodeURIComponent(topic.tag_id)}`}
                className="underline underline-offset-2"
              >
                {topic.name_de}
              </Link>
              <Confidence value={topic.confidence} />
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

function Results({ query, page }: { query: string; page: number }) {
  const offset = (page - 1) * LIMIT
  const found = useApi<SearchResult>(
    `/v1/search?q=${encodeURIComponent(query)}&limit=${LIMIT}&offset=${offset}`
  )
  const link = (target: number) =>
    `/suche?q=${encodeURIComponent(query)}${target > 1 ? `&seite=${target}` : ""}`

  if (found.loading) return <Skeleton className="h-40 w-full" />
  if (found.error || !found.data) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Suche fehlgeschlagen</AlertTitle>
        <AlertDescription>{found.error}</AlertDescription>
      </Alert>
    )
  }
  const { total, items } = found.data
  if (total === 0) {
    return (
      <p className="text-muted-foreground">
        Keine Geschäfte gefunden. Versuche ein anderes Stichwort oder stöbere in
        der{" "}
        <Link to="/" className="underline underline-offset-2">
          Themenübersicht
        </Link>
        .
      </p>
    )
  }
  const last = Math.ceil(total / LIMIT)
  return (
    <>
      <p className="text-xs text-muted-foreground">
        {total} Treffer, Seite {page} von {last}
      </p>
      <ul>
        {items.map((hit) => (
          <Hit key={hit.affair_id} hit={hit} />
        ))}
      </ul>
      <nav aria-label="Seiten" className="flex gap-4 text-sm">
        {page > 1 && (
          <Link to={link(page - 1)} className="underline underline-offset-2">
            Zurück
          </Link>
        )}
        {page < last && (
          <Link to={link(page + 1)} className="underline underline-offset-2">
            Weiter
          </Link>
        )}
      </nav>
    </>
  )
}

// Volltextsuche über Titel und Texte (GET /v1/search). Die Suche in eigenen Worten durch einen
// Agenten kommt später dazu.
export function SearchPage() {
  const { search } = useLocation()
  const params = new URLSearchParams(search)
  const query = params.get("q")?.trim() ?? ""
  const page = Math.max(1, Number.parseInt(params.get("seite") ?? "1", 10) || 1)
  usePageTitle(query ? `Suche: ${query}` : "Suche")
  return (
    <>
      <div className="flex flex-col gap-3">
        <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
          Suche
        </h1>
        <SearchForm key={query} initial={query} />
      </div>
      <section aria-live="polite" className="flex flex-col gap-2">
        {query.length >= 2 ? (
          <Results key={`${query}|${page}`} query={query} page={page} />
        ) : (
          <p className="max-w-[68ch] text-muted-foreground">
            Gib mindestens zwei Zeichen ein. «Wortfolge» in Anführungszeichen
            sucht die Wörter nebeneinander, -wort schliesst ein Wort aus, or
            sucht das eine oder das andere.
          </p>
        )}
      </section>
    </>
  )
}
