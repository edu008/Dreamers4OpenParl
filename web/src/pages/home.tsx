import { XIcon } from "lucide-react"
import { Fragment, useState, type ReactNode } from "react"
import { Link, useLocation, useNavigate } from "react-router"

import { SearchForm } from "@/components/search-form"
import { Segmented } from "@/components/segmented"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog"
import { GradientBlobCard } from "@/components/ui/gradient-blob-card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import { usePageTitle } from "@/hooks/use-page-title"
import { useQuery } from "@/hooks/use-query"
import type {
  BodyOut,
  SearchHit,
  SearchLanguage,
  SearchResult,
  TopicOut,
} from "@/lib/api"
import { LEVEL_LABEL } from "@/lib/export"
import { parseSnippet } from "@/lib/snippet"
import {
  AffairFacts,
  affairMeta,
  useAffair,
  type AffairLink,
} from "@/pages/affair-facts"

const LIMIT = 20
const TOPICS_SHOWN = 3
const number = new Intl.NumberFormat("de-CH")

const LEVELS = ["country", "canton", "city", "municipality"]
const LANGUAGES = [
  { value: "de", label: "Deutsch" },
  { value: "fr", label: "Französisch" },
  { value: "it", label: "Italienisch" },
]
// Adresse (deutsch, zum Teilen) → Parameter von GET /v1/search.
const API_PARAM: Record<string, string> = {
  q: "q",
  thema: "topic",
  parlament: "body_key",
  ebene: "level",
  sprache: "language",
  von: "from",
  bis: "to",
}
const FILTERS = ["thema", "parlament", "ebene", "sprache", "von", "bis"]

/** Wert aus der Adresse, nur wenn die API ihn annimmt; so führt eine kaputte Adresse nie zu 422. */
function valid(params: URLSearchParams, key: string): string | null {
  const value = params.get(key)?.trim()
  if (!value) return null
  if (key === "q")
    return value.length >= 2 && value.length <= 200 ? value : null
  if (key === "ebene") return LEVELS.includes(value) ? value : null
  if (key === "sprache") {
    return LANGUAGES.some((language) => language.value === value) ? value : null
  }
  if (key === "von" || key === "bis") {
    return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null
  }
  return value
}

/** Ein Parameter neu gesetzt (null löscht ihn); jede Änderung führt zurück auf Seite 1. */
function withParam(
  params: URLSearchParams,
  key: string,
  value: string | null
): URLSearchParams {
  const next = new URLSearchParams(params)
  if (value) next.set(key, value)
  else next.delete(key)
  next.delete("seite")
  return next
}

/** Kürzel rechts auf der Karte: Bund und Kantone haben eines (CHE, ZH), Städte und Gemeinden
 * nur eine BFS-Nummer; dort steht die Ebene. Keine Kantonswappen (Wappenschutz). */
function bodyTile(hit: SearchHit): string {
  if (/^[A-Z]{2,3}$/.test(hit.body_key)) return hit.body_key
  return hit.body_level === "municipality" ? "Gde." : "Stadt"
}

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
          <mark
            key={index}
            className="bg-transparent font-bold text-foreground"
          >
            {part.text}
          </mark>
        ) : (
          part.text
        )
      )}
    </p>
  )
}

function Hit({ hit, params }: { hit: SearchHit; params: URLSearchParams }) {
  // Öffnet das Pop-up über die Adresse: Zurück schliesst es, der Link lässt sich teilen.
  const popup = new URLSearchParams(params)
  popup.set("geschaeft", String(hit.affair_id))
  const title = hit.title ?? `Geschäft ${hit.affair_id}`
  const meta = [
    hit.type_de ?? hit.type,
    hit.number && `Nr. ${hit.number}`,
    hit.body_name ?? hit.body_key,
  ]
  const more = hit.topics.length - TOPICS_SHOWN
  return (
    <li className="group relative grid gap-x-8 gap-y-2 border-t border-border py-6 first:border-t-0 sm:grid-cols-[8rem_minmax(0,1fr)]">
      {/* Linke Spalte im Raster: Datum und Parlament, wie in einem Register. */}
      <p className="flex gap-3 text-sm sm:flex-col sm:gap-1">
        <span className="tabular text-base font-bold">
          {formatDate(hit.begin_date)}
        </span>
        <span
          className="font-bold text-muted-foreground"
          title={hit.body_name ?? undefined}
        >
          {bodyTile(hit)}
        </span>
      </p>
      {/* break-words: Quelltexte enthalten Trennlinien wie «_____» ohne Leerzeichen. */}
      <div className="flex min-w-0 flex-col gap-2 break-words">
        <p className="tabular text-sm text-muted-foreground">
          {meta.filter(Boolean).join(" · ")}
        </p>
        <h2 className="text-base leading-snug font-bold text-balance group-hover:text-primary sm:text-lg">
          {/* Die ganze Zeile ist der Link (::after deckt sie ab); die Themen liegen darüber. */}
          <Link
            to={{ search: `?${popup}` }}
            state={{ popup: true }}
            className="outline-none after:absolute after:inset-0 focus-visible:after:outline-2 focus-visible:after:outline-offset-2 focus-visible:after:outline-ring"
          >
            {title}
          </Link>
        </h2>
        {hit.headline && <Snippet headline={hit.headline} />}
        {hit.topics.length > 0 && (
          <ul
            aria-label="Themen"
            className="relative z-10 flex flex-wrap items-center gap-2 pt-1"
          >
            {hit.topics.slice(0, TOPICS_SHOWN).map((topic) => (
              <li key={topic.tag_id}>
                <Link
                  to={{
                    search: `?${withParam(params, "thema", topic.tag_id)}`,
                  }}
                  className="inline-flex min-h-8 items-center border border-foreground px-2.5 text-sm transition-colors hover:bg-foreground hover:text-background"
                >
                  {topic.name_de}
                </Link>
              </li>
            ))}
            {more > 0 && (
              <li className="text-sm text-muted-foreground">+{more} weitere</li>
            )}
          </ul>
        )}
      </div>
    </li>
  )
}

/** Thema als entfernbarer Filter; der Name kommt aus GET /v1/topics. */
function TopicChip({
  params,
  tagId,
}: {
  params: URLSearchParams
  tagId: string
}) {
  const topics = useApi<TopicOut[]>("/v1/topics")
  const name =
    topics.data?.find((topic) => topic.tag_id === tagId)?.name_de ?? tagId
  return (
    <Link
      to={{ search: `?${withParam(params, "thema", null)}` }}
      aria-label={`Filter Thema ${name} entfernen`}
      className="inline-flex min-h-10 items-center gap-2 self-start bg-foreground px-4 text-sm font-bold text-background transition-colors hover:bg-primary"
    >
      Thema: {name}
      <span aria-hidden className="text-base leading-none">
        ×
      </span>
    </Link>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-semibold">{label}</span>
      {children}
    </div>
  )
}

function Filters({
  params,
  onChange,
}: {
  params: URLSearchParams
  onChange: (key: string, value: string | null) => void
}) {
  const bodies = useApi<BodyOut[]>("/v1/bodies")
  const level = valid(params, "ebene")
  const shown = (bodies.data ?? []).filter(
    (body) => !level || body.level === level
  )
  const groups = LEVELS.map((key) => ({
    key,
    bodies: shown
      .filter((body) => body.level === key)
      .sort((a, b) =>
        (a.name ?? a.body_key).localeCompare(b.name ?? b.body_key)
      ),
  })).filter((group) => group.bodies.length > 0)
  return (
    <div id="filter" className="grid gap-6 bg-muted p-6 sm:grid-cols-2">
      <Field label="Ebene">
        <Segmented
          label="Ebene"
          options={[
            { value: "", label: "Alle" },
            ...LEVELS.map((key) => ({ value: key, label: LEVEL_LABEL[key] })),
          ]}
          value={level ?? ""}
          onChange={(value) => onChange("ebene", value || null)}
        />
      </Field>
      <Field label="Sprache">
        <Segmented
          label="Sprache"
          options={[{ value: "", label: "Alle" }, ...LANGUAGES]}
          value={valid(params, "sprache") ?? ""}
          onChange={(value) => onChange("sprache", value || null)}
        />
      </Field>
      <label className="flex flex-col gap-2">
        <span className="text-sm font-semibold">Parlament</span>
        <select
          value={params.get("parlament") ?? ""}
          onChange={(event) =>
            onChange("parlament", event.target.value || null)
          }
          className="h-11 border border-input bg-background px-3 text-sm"
        >
          <option value="">Alle Parlamente</option>
          {groups.map((group) => (
            <optgroup key={group.key} label={LEVEL_LABEL[group.key]}>
              {group.bodies.map((body) => (
                <option key={body.body_key} value={body.body_key}>
                  {body.name ?? body.body_key}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>
      <fieldset className="flex flex-col gap-2">
        <legend className="pb-2 text-sm font-semibold">Zeitraum</legend>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="date"
            aria-label="von"
            value={valid(params, "von") ?? ""}
            onChange={(event) => onChange("von", event.target.value || null)}
            className="h-11 w-auto flex-1"
          />
          <span className="text-sm text-muted-foreground">bis</span>
          <Input
            type="date"
            aria-label="bis"
            value={valid(params, "bis") ?? ""}
            onChange={(event) => onChange("bis", event.target.value || null)}
            className="h-11 w-auto flex-1"
          />
        </div>
      </fieldset>
    </div>
  )
}

function pageLink(params: URLSearchParams, target: number) {
  const next = new URLSearchParams(params)
  if (target > 1) next.set("seite", String(target))
  else next.delete("seite")
  return { search: `?${next}` }
}

const SEARCH_LANGUAGES: SearchLanguage[] = ["de", "fr", "it"]
const TEXT_LINK = "underline underline-offset-2 hover:text-primary"

/** «A», «A und B», «A, B und C». */
function joined(parts: ReactNode[]): ReactNode {
  return parts.map((part, index) => (
    <Fragment key={index}>
      {index > 0 && (index === parts.length - 1 ? " und " : ", ")}
      {part}
    </Fragment>
  ))
}

// Wie die Suche die Eingabe verstanden hat, als ein Satz unter der Trefferzahl (wie «Ergebnisse
// für …, stattdessen nach … suchen»): erkannte Themen als Link auf den Themenfilter, die
// bevorzugte Bezeichnung je weiterer Sprache und der Weg zur wörtlichen Suche. Text statt Symbol.
function Understood({
  params,
  query,
  result,
}: {
  params: URLSearchParams
  query: string
  result: SearchResult
}) {
  const link = (key: string, value: string | null) => ({
    search: `?${withParam(params, key, value)}`,
  })
  if (params.get("wortlaut") === "1") {
    return (
      <p>
        Wörtlich gesucht, ohne Themenerkennung.{" "}
        <Link to={link("wortlaut", null)} className={TEXT_LINK}>
          Mit Themenerkennung suchen
        </Link>
      </p>
    )
  }
  const topics = result.topics ?? []
  if (topics.length === 0) return null
  // Was der Satz schon nennt (Thema, Eingabe), steht nicht noch einmal als Beispiel da.
  const named = new Set(
    topics
      .flatMap((topic) => [topic.name_de, topic.typed, topic.label])
      .map((text) => text?.toLowerCase())
  )
  const examples = SEARCH_LANGUAGES.map(
    (language) => result.expanded_terms?.[language]?.[0]
  ).filter((term): term is string => !!term && !named.has(term.toLowerCase()))
  return (
    <p>
      Verstanden als {topics.length > 1 ? "Themen" : "Thema"}{" "}
      {joined(
        topics.map((topic) => (
          <>
            <Link to={link("thema", topic.tag_id)} className={TEXT_LINK}>
              {topic.name_de}
            </Link>
            {topic.source === "llm" && " (Vorschlag des Sprachmodells)"}
          </>
        ))
      )}
      {examples.length > 0 && (
        <>: auch {joined(examples.map((term) => `«${term}»`))} gesucht</>
      )}
      .{" "}
      <Link to={link("wortlaut", "1")} className={TEXT_LINK}>
        Nur «{query}» suchen
      </Link>
    </p>
  )
}

function Results({
  params,
  query,
  page,
}: {
  params: URLSearchParams
  query: string | null
  page: number
}) {
  const api = new URLSearchParams()
  for (const [key, name] of Object.entries(API_PARAM)) {
    const value = valid(params, key)
    if (value) api.set(name, value)
  }
  if (params.get("wortlaut") === "1") api.set("expand", "false")
  api.set("limit", String(LIMIT))
  api.set("offset", String((page - 1) * LIMIT))
  const found = useApi<SearchResult>(`/v1/search?${api}`)

  if (found.loading) {
    return (
      <div className="flex flex-col gap-4" aria-busy>
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
    )
  }
  if (found.error || !found.data) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Suche fehlgeschlagen</AlertTitle>
        <AlertDescription>{found.error}</AlertDescription>
      </Alert>
    )
  }
  const { total, items } = found.data
  const last = Math.max(1, Math.ceil(total / LIMIT))
  return (
    <>
      <div
        aria-live="polite"
        className="flex flex-col gap-1 text-sm text-muted-foreground"
      >
        <p>
          {query
            ? `${number.format(total)} Treffer für «${query}»`
            : `${number.format(total)} Geschäfte, neueste zuerst`}
        </p>
        {query && (
          <Understood params={params} query={query} result={found.data} />
        )}
      </div>
      {total === 0 ? (
        <p className="max-w-[60ch] text-lg">
          Keine Geschäfte gefunden. Versuche ein anderes Stichwort oder weniger
          Filter.
        </p>
      ) : (
        <ol className="border-y-2 border-foreground">
          {items.map((hit) => (
            <Hit key={hit.affair_id} hit={hit} params={params} />
          ))}
        </ol>
      )}
      {last > 1 && (
        <nav
          aria-label="Seiten"
          className="flex items-center justify-between gap-4 pt-2"
        >
          {page > 1 ? (
            <Button
              variant="outline"
              nativeButton={false}
              render={<Link to={pageLink(params, page - 1)} />}
            >
              Zurück
            </Button>
          ) : (
            <span />
          )}
          <span className="tabular text-sm text-muted-foreground">
            Seite {number.format(page)} von {number.format(last)}
          </span>
          {page < last ? (
            <Button
              variant="outline"
              nativeButton={false}
              render={<Link to={pageLink(params, page + 1)} />}
            >
              Weiter
            </Button>
          ) : (
            <span />
          )}
        </nav>
      )}
    </>
  )
}

// Öffentliche Startseite: eine Aufgabe, Geschäfte finden. Ein Suchfeld, Filter hinter einem
// Schalter, darunter die neuesten Geschäfte oder die Treffer (GET /v1/search, mit oder ohne q).
/** Ein Geschäft als Pop-up über der Liste, in der GradientBlobCard. */
function AffairPopup({
  affairId,
  onClose,
}: {
  affairId: string
  onClose: () => void
}) {
  const found = useAffair(affairId)
  const [params] = useQuery()
  // Ein verwandtes Geschäft ersetzt das offene im selben Pop-up (replace: X führt zur Liste).
  const link: AffairLink = (id) => {
    const next = new URLSearchParams(params)
    next.set("geschaeft", String(id))
    return { to: { search: `?${next}` }, replace: true, state: { popup: true } }
  }
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-3xl" showCloseButton={false}>
        <GradientBlobCard>
          {/* Ein Scrollbereich im Glas; die Kopfzeile steht darin oben fest, damit der erste
              Fokus (der X) im Scrollbereich liegt und Pfeiltasten sofort scrollen. Der key
              setzt das Scrollen zurück, wenn ein verwandtes Geschäft geöffnet wird. */}
          <div
            key={affairId}
            className="max-h-[90dvh] [scrollbar-gutter:stable] overflow-y-auto overscroll-contain sm:max-h-[85dvh]"
          >
            <div className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b-2 border-foreground bg-background px-5 py-2 sm:px-9">
              <p className="tabular min-w-0 truncate text-sm text-muted-foreground">
                {found.data && affairMeta(found.data)}
              </p>
              <DialogClose
                render={
                  <Button
                    variant="outline"
                    size="icon"
                    title="Schliessen (Esc)"
                  />
                }
              >
                <XIcon className="size-5" />
                <span className="sr-only">Schliessen</span>
              </DialogClose>
            </div>
            <div className="p-5 sm:p-9">
              <AffairFacts found={found} Title={DialogTitle} link={link} />
            </div>
          </div>
        </GradientBlobCard>
      </DialogContent>
    </Dialog>
  )
}

export function HomePage() {
  const [params, setParams] = useQuery()
  const typed = params.get("q")?.trim() ?? ""
  const query = valid(params, "q")
  const topic = valid(params, "thema")
  const page = Math.max(1, Number.parseInt(params.get("seite") ?? "1", 10) || 1)
  const active = FILTERS.filter((key) => valid(params, key)).length
  const [open, setOpen] = useState(active > 0)
  usePageTitle(query ? `Suche: ${query}` : "Geschäfte")
  const affairId = params.get("geschaeft")?.trim()
  const navigate = useNavigate()
  const openedHere = (useLocation().state as { popup?: boolean } | null)?.popup

  function closeAffair() {
    // Aus der Liste geöffnet: einen Schritt zurück, damit Zurück nicht wieder öffnet.
    if (openedHere) return navigate(-1)
    const next = new URLSearchParams(params)
    next.delete("geschaeft")
    setParams(next)
  }

  function reset() {
    const next = new URLSearchParams()
    if (typed) next.set("q", typed)
    // Keine Filter, sondern die Art der Suche: bleibt stehen.
    if (params.get("wortlaut") === "1") next.set("wortlaut", "1")
    setParams(next)
  }

  return (
    <>
      <section className="flex flex-col gap-6 pt-2 pb-2 sm:pt-6">
        <h1 className="font-heading text-[clamp(3rem,9vw,6.5rem)] leading-[0.9] font-bold tracking-[-0.04em]">
          Geschäfte finden
        </h1>
        <p className="max-w-[44ch] text-lg leading-relaxed sm:text-xl">
          Alle Geschäfte aus den Parlamenten von Bund, Kantonen und Gemeinden,
          nach Themen geordnet.
        </p>
        <SearchForm key={typed} initial={typed} />
        {typed.length === 1 && (
          <p className="text-sm text-muted-foreground">
            Gib mindestens zwei Zeichen ein. Unten stehen die neuesten
            Geschäfte.
          </p>
        )}
      </section>

      <section aria-label="Geschäfte" className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            aria-expanded={open}
            aria-controls="filter"
            onClick={() => setOpen(!open)}
          >
            {open ? "Filter ausblenden" : "Filter einblenden"}
            {active > 0 && ` (${active})`}
          </Button>
          {active > 0 && (
            <Button variant="ghost" onClick={reset}>
              Filter zurücksetzen
            </Button>
          )}
          {topic && <TopicChip params={params} tagId={topic} />}
        </div>
        {open && (
          <Filters
            params={params}
            onChange={(key, value) => setParams(withParam(params, key, value))}
          />
        )}
        <Results params={params} query={query} page={page} />
        {affairId && <AffairPopup affairId={affairId} onClose={closeAffair} />}
      </section>
    </>
  )
}
