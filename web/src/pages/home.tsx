import { useState, type ReactNode } from "react"
import { Link, useLocation } from "react-router"

import { Confidence } from "@/components/confidence"
import { SearchForm } from "@/components/search-form"
import { Segmented } from "@/components/segmented"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import { usePageTitle } from "@/hooks/use-page-title"
import { useQuery } from "@/hooks/use-query"
import type { BodyOut, SearchHit, SearchResult, TopicOut } from "@/lib/api"
import { LEVEL_LABEL } from "@/lib/export"
import { parseSnippet } from "@/lib/snippet"

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
            className="rounded-sm bg-muted px-0.5 font-semibold text-foreground"
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
  const { search } = useLocation()
  const title = hit.title ?? `Geschäft ${hit.affair_id}`
  const meta = [
    hit.type_de ?? hit.type,
    hit.number && `Nr. ${hit.number}`,
    formatDate(hit.begin_date),
    hit.body_name ?? hit.body_key,
  ]
  const more = hit.topics.length - TOPICS_SHOWN
  return (
    <li className="relative flex gap-5 rounded-clay bg-card p-5 shadow-clay transition-[translate,box-shadow] duration-200 hover:shadow-clay-raised motion-safe:hover:-translate-y-0.5 sm:p-6">
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <p className="tabular text-sm text-muted-foreground">
          {meta.filter(Boolean).join(" · ")}
        </p>
        <h2 className="text-lg leading-snug font-semibold text-balance sm:text-xl">
          {/* Die ganze Karte ist der Link (::after deckt sie ab); die Themen liegen darüber. */}
          <Link
            to={`/geschaefte/${hit.affair_id}`}
            state={{ search }}
            className="outline-none after:absolute after:inset-0 after:rounded-clay focus-visible:after:outline-2 focus-visible:after:outline-offset-2 focus-visible:after:outline-ring"
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
                  className="inline-flex min-h-8 items-center gap-2 rounded-full bg-muted px-3 text-sm shadow-clay-pressed transition-colors hover:bg-secondary"
                >
                  {topic.name_de}
                  <Confidence value={topic.confidence} />
                </Link>
              </li>
            ))}
            {more > 0 && (
              <li className="text-sm text-muted-foreground">+{more} weitere</li>
            )}
          </ul>
        )}
      </div>
      <span
        aria-hidden
        title={hit.body_name ?? undefined}
        className="hidden size-14 shrink-0 items-center justify-center rounded-2xl bg-muted text-xs font-bold tracking-tight shadow-clay-pressed sm:flex"
      >
        {bodyTile(hit)}
      </span>
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
      className="inline-flex min-h-9 items-center gap-2 self-start rounded-full bg-card px-4 text-sm font-medium shadow-clay transition-shadow hover:shadow-clay-raised"
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
    <div
      id="filter"
      className="grid gap-6 rounded-clay bg-card p-6 shadow-clay sm:grid-cols-2"
    >
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
          className="h-11 rounded-full border border-input bg-muted px-4 text-sm shadow-clay-pressed"
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
  api.set("limit", String(LIMIT))
  api.set("offset", String((page - 1) * LIMIT))
  const found = useApi<SearchResult>(`/v1/search?${api}`)

  if (found.loading) {
    return (
      <div className="flex flex-col gap-4" aria-busy>
        <Skeleton className="h-32 rounded-clay" />
        <Skeleton className="h-32 rounded-clay" />
        <Skeleton className="h-32 rounded-clay" />
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
      <p aria-live="polite" className="text-sm text-muted-foreground">
        {query
          ? `${number.format(total)} Treffer für «${query}»`
          : `${number.format(total)} Geschäfte, neueste zuerst`}
      </p>
      {total === 0 ? (
        <p className="max-w-[60ch] text-lg">
          Keine Geschäfte gefunden. Versuche ein anderes Stichwort oder weniger
          Filter.
        </p>
      ) : (
        <ol className="flex flex-col gap-4">
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
export function HomePage() {
  const [params, setParams] = useQuery()
  const typed = params.get("q")?.trim() ?? ""
  const query = valid(params, "q")
  const topic = valid(params, "thema")
  const page = Math.max(1, Number.parseInt(params.get("seite") ?? "1", 10) || 1)
  const active = FILTERS.filter((key) => valid(params, key)).length
  const [open, setOpen] = useState(active > 0)
  usePageTitle(query ? `Suche: ${query}` : "Geschäfte")

  function reset() {
    const next = new URLSearchParams()
    if (typed) next.set("q", typed)
    setParams(next)
  }

  return (
    <>
      <section className="flex flex-col gap-6 pt-4 pb-2 sm:pt-10">
        <h1 className="font-heading text-[clamp(2.5rem,7vw,5rem)] leading-[0.95] font-bold tracking-[-0.035em]">
          Geschäfte finden
        </h1>
        <p className="max-w-[46ch] text-lg leading-relaxed sm:text-xl">
          In allen Parlamenten von Bund, Kantonen und Gemeinden. Jedes Thema
          zeigt die Textstelle, die es begründet.
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
      </section>
    </>
  )
}
