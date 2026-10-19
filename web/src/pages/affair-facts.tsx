import {
  useEffect,
  useRef,
  useState,
  type ElementType,
  type ReactNode,
} from "react"
import { Link, useLocation, useParams, type LinkProps } from "react-router"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import { usePageTitle } from "@/hooks/use-page-title"
import {
  fetchJson,
  type AffairRecord,
  type AffairStar,
  type AffairTopics,
  type DocList,
  type Localized,
} from "@/lib/api"
import { LEVEL_LABEL } from "@/lib/export"
import { paragraphsOf } from "@/pages/affair"

const LANGUAGE_NAME: Record<string, string> = {
  de: "Deutsch",
  fr: "Französisch",
  it: "Italienisch",
  rm: "Rätoromanisch",
}

// Lesbare Namen der Formate in affair_docs (Stand 19.10.2026); andere bleiben ohne Angabe.
const FORMAT_NAME: Record<string, string> = {
  "application/pdf": "PDF",
  pdf: "PDF",
  "text/html": "HTML",
  "video/sonomix": "Video",
  "application/msword": "Word",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
    "Word",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel",
  "application/rtf": "RTF",
  "application/zip": "ZIP",
  "text/plain": "Text",
}

// Höchstes limit von GET /v1/affairs/{id}/docs.
const DOCS_PAGE = 200

// Zeile im Raster der Fakten und Dokumente: Begriff links, Wert rechts.
const ROW =
  "grid gap-x-6 gap-y-1 border-t border-border py-3 first:border-t-0 first:pt-0 @md:grid-cols-[10rem_minmax(0,1fr)]"

function formatDate(iso: string | null | undefined): string {
  if (!iso) return ""
  const [year, month, day] = iso.slice(0, 10).split("-")
  return `${day}.${month}.${year}`
}

/** Erste gefüllte Sprache in der Reihenfolge de, fr, it, rm, en. */
function firstLanguage(field: Localized | undefined): string | undefined {
  return field?.de || field?.fr || field?.it || field?.rm || field?.en
}

function fileSize(bytes: number): string {
  return bytes < 1e6
    ? `${Math.max(1, Math.round(bytes / 1e3))} kB`
    : `${(bytes / 1e6).toFixed(1)} MB`
}

/** Kurzangabe wie bei OpenParlData: «Geschäft | Nr. … | Datum | Typ». Seite und Pop-up setzen
 * sie selbst (im Pop-up in die Kopfzeile, die beim Scrollen stehen bleibt). */
export function affairMeta(affair: AffairTopics): string {
  return [
    "Geschäft",
    affair.number && `Nr. ${affair.number}`,
    formatDate(affair.begin_date),
    affair.type_de ?? affair.type,
  ]
    .filter(Boolean)
    .join(" | ")
}

/** Abschnitt im Raster: Titel in der linken Spalte, Inhalt rechts. */
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid gap-x-8 gap-y-3 border-t-2 border-foreground pt-4 @3xl:grid-cols-[12rem_minmax(0,1fr)]">
      <h2 className="text-base font-bold">{title}</h2>
      <div className="min-w-0">{children}</div>
    </section>
  )
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl>
      {rows.map(([term, value]) => (
        <div key={term} className={ROW}>
          <dt className="text-sm font-bold">{term}</dt>
          <dd className="min-w-0 text-sm break-words">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

/** Dokumente als Links zum Parlament (die Web-App lädt nichts davon); «Alle n» holt den Rest. */
function Documents({ record }: { record: AffairRecord }) {
  const [docs, setDocs] = useState(record.docs)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>()
  const firstNew = useRef<HTMLAnchorElement>(null)

  // Der Knopf verschwindet nach dem Laden; der Fokus springt zum ersten neuen Dokument.
  useEffect(() => firstNew.current?.focus(), [docs.length])

  async function loadAll() {
    if (loading) return
    setLoading(true)
    setError(undefined)
    try {
      const all = [...docs]
      while (all.length < record.n_docs) {
        const page = await fetchJson<DocList>(
          `/v1/affairs/${record.id}/docs?limit=${DOCS_PAGE}&offset=${all.length}`
        )
        if (page.items.length === 0) break
        all.push(...page.items)
      }
      setDocs(all)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <ul>
        {docs.map((doc, index) => {
          const name = doc.name || "Dokument"
          const file = [
            doc.format && FORMAT_NAME[doc.format],
            doc.size && fileSize(doc.size),
          ]
            .filter(Boolean)
            .join(", ")
          const details = [firstLanguage(doc.category), file]
            .filter(Boolean)
            .join(" · ")
          return (
            <li key={doc.id} className={ROW}>
              {/* OpenParlData setzt 1900-01-01 (selten Tippfehler wie 0202), wenn das Datum fehlt. */}
              <span className="tabular text-sm font-bold">
                {doc.date && doc.date >= "1901"
                  ? formatDate(doc.date)
                  : "ohne Datum"}
              </span>
              <div className="min-w-0 text-sm break-words">
                {doc.url ? (
                  <a
                    ref={index === record.docs.length ? firstNew : undefined}
                    href={doc.url}
                    className="underline underline-offset-4 hover:text-primary"
                  >
                    {name}
                  </a>
                ) : (
                  name
                )}
                {details && <p className="text-muted-foreground">{details}</p>}
              </div>
            </li>
          )
        })}
      </ul>
      {docs.length < record.n_docs && (
        <Button
          variant="outline"
          className="self-start"
          onClick={() => void loadAll()}
        >
          {loading ? "Dokumente laden …" : `Alle ${record.n_docs} Dokumente`}
        </Button>
      )}
      {error && (
        <p role="alert" className="text-sm">
          Weitere Dokumente nicht geladen: {error}
        </p>
      )}
    </div>
  )
}

/** Ziel eines Links auf ein anderes Geschäft: auf der Seite /geschaefte/<id>, im Pop-up dasselbe
 * Pop-up mit dem anderen Geschäft. */
export type AffairLink = (
  id: number
) => Pick<LinkProps, "to" | "replace" | "state">

const PAGE_LINK: AffairLink = (id) => ({ to: `/geschaefte/${id}` })

/** Verwandte Geschäfte über gemeinsame aktive Themen (GET /v1/graph/affairs/{id}). Ein Zusatz:
 * fehlt er oder schlägt er fehl, bleibt der Abschnitt weg. */
function Related({ affairId, link }: { affairId: number; link: AffairLink }) {
  const star = useApi<AffairStar>(`/v1/graph/affairs/${affairId}?limit=5`)
  const neighbours = star.data?.neighbours ?? []
  if (neighbours.length === 0) return null
  const names = new Map(
    star.data?.center.topics.map((topic) => [topic.tag_id, topic.name_de])
  )
  return (
    <Section title="Verwandte Geschäfte">
      <ul>
        {neighbours.map((neighbour) => {
          const shared = neighbour.shared.map((id) => names.get(id) ?? id)
          const meta = [
            neighbour.type_de ?? neighbour.type,
            neighbour.number && `Nr. ${neighbour.number}`,
            neighbour.body_name ?? neighbour.body_key,
            formatDate(neighbour.begin_date),
          ]
          return (
            <li
              key={neighbour.affair_id}
              className="flex flex-col gap-1 border-t border-border py-3 first:border-t-0 first:pt-0"
            >
              <Link
                {...link(neighbour.affair_id)}
                className="text-sm leading-snug font-bold underline-offset-4 hover:text-primary hover:underline"
              >
                {neighbour.title ?? `Geschäft ${neighbour.affair_id}`}
              </Link>
              <p className="tabular text-sm text-muted-foreground">
                {meta.filter(Boolean).join(" · ")}
              </p>
              <p className="text-sm text-muted-foreground">
                Gemeinsam: {shared.join(", ")}
              </p>
            </li>
          )
        })}
      </ul>
    </Section>
  )
}

/** Themen und bereinigter Text (…/topics) und der gespeicherte Datensatz mit Dokumenten. */
export function useAffair(affairId: string) {
  const path = `/v1/affairs/${encodeURIComponent(affairId)}`
  const topics = useApi<AffairTopics>(`${path}/topics`)
  const record = useApi<AffairRecord>(path)
  // Ein Ladezustand für beide, damit die Abschnitte nicht nachrutschen.
  return { ...topics, loading: topics.loading || record.loading, record }
}

// Öffentliche Geschäftsseite (direkter Link): Rückweg zur Suche und die Fakten.
export function AffairFactsPage() {
  const { affairId = "" } = useParams()
  const fromSearch = (useLocation().state as { search?: string } | null)?.search
  const found = useAffair(affairId)
  usePageTitle(found.data?.title ?? "Geschäft")
  return (
    <article className="flex flex-col gap-10">
      <Link
        to={{ pathname: "/", search: fromSearch ?? "" }}
        className="self-start text-sm font-bold underline-offset-4 hover:text-primary hover:underline"
      >
        ← Geschäfte
      </Link>
      <div className="flex flex-col gap-4">
        {found.data && (
          <p className="tabular text-sm text-muted-foreground">
            {affairMeta(found.data)}
          </p>
        )}
        <AffairFacts found={found} />
      </div>
    </article>
  )
}

// Die Fakten wie bei OpenParlData und die Themen, ohne Konfidenz, Modell oder Prüfstand (die
// Prüfansicht liegt unter /admin/review). Seite und Pop-up nutzen sie; im Pop-up ist der Titel
// der Dialog-Titel.
export function AffairFacts({
  found,
  Title = "h1",
  link = PAGE_LINK,
}: {
  found: ReturnType<typeof useAffair>
  Title?: ElementType
  link?: AffairLink
}) {
  if (found.loading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (found.error || !found.data) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Geschäft nicht geladen</AlertTitle>
        <AlertDescription>{found.error}</AlertDescription>
      </Alert>
    )
  }

  const affair = found.data
  const record = found.record.data
  const body = record?.body
  const title = affair.title ?? `Geschäft ${affair.affair_id}`
  const type = affair.type_de ?? affair.type
  const language = affair.language ?? "de"
  const paragraphs = paragraphsOf(affair.text)
  const topics = affair.labels.filter((label) => label.status === "active")

  const details: [string, ReactNode][] = [
    ["ID", <span className="tabular">{affair.affair_id}</span>],
  ]
  if (record?.external_id) details.push(["Externe ID", record.external_id])
  if (affair.number) details.push(["Nummer", affair.number])
  details.push(["Titel", <span lang={language}>{title}</span>])
  const titleLong = firstLanguage(record?.title_long)
  if (titleLong && titleLong !== affair.title) {
    details.push(["Langer Titel", <span lang={language}>{titleLong}</span>])
  }
  // Harmonisierter Typ, dahinter der Typ, wie ihn das Parlament nennt.
  const ownType = firstLanguage(record?.type_name)
  const typeText =
    type && ownType && ownType !== type
      ? `${type} (${ownType})`
      : (type ?? ownType)
  if (typeText) details.push(["Typ", typeText])
  const state =
    firstLanguage(record?.state_name_harmonized) ||
    firstLanguage(record?.state_name)
  if (state) details.push(["Stand", state])
  if (affair.begin_date) details.push(["Beginn", formatDate(affair.begin_date)])
  if (record?.end_date) details.push(["Ende", formatDate(record.end_date)])
  if (affair.url_external) {
    details.push([
      "URL",
      <a
        href={affair.url_external}
        className="break-all underline underline-offset-4 hover:text-primary"
      >
        {affair.url_external}
      </a>,
    ])
  }

  const area: [string, ReactNode][] = [
    ["Parlament", affair.body_name ?? affair.body_key],
  ]
  const council = firstLanguage(body?.legislative_name)
  if (council) area.push(["Gremium", council])
  const level =
    (affair.body_level && LEVEL_LABEL[affair.body_level]) ||
    firstLanguage(body?.type_name) ||
    affair.body_level
  if (level) area.push(["Ebene", level])
  if (body?.canton_key) area.push(["Kanton", body.canton_key])
  if (body?.languages) {
    const names = body.languages
      .split(",")
      .map((code) => code.trim())
      .map((code) => LANGUAGE_NAME[code.toLowerCase()] ?? code)
    area.push([
      names.length > 1 ? "Amtssprachen" : "Amtssprache",
      names.join(", "),
    ])
  }

  return (
    <div className="@container flex flex-col gap-10">
      <header className="flex flex-col gap-4">
        {/* Grösse nach Containerbreite (cqi), nicht nach Fenster: im Pop-up kleiner als auf der Seite. */}
        <Title
          lang={language}
          className="font-heading text-[length:clamp(1.5rem,4cqi,2.5rem)] leading-[1.1] font-bold tracking-[-0.02em] text-balance"
        >
          {title}
        </Title>
        {topics.length > 0 && (
          <ul aria-label="Themen" className="flex flex-wrap gap-2">
            {topics.map((topic) => (
              <li key={topic.id}>
                <Link
                  to={`/?thema=${encodeURIComponent(topic.tag_id)}`}
                  className="inline-flex min-h-8 items-center bg-foreground px-2.5 text-sm font-bold text-background transition-colors hover:bg-primary"
                >
                  {topic.name_de}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </header>

      {found.record.error && (
        <Alert variant="destructive">
          <AlertTitle>Dokumente und weitere Angaben nicht geladen</AlertTitle>
          <AlertDescription>{found.record.error}</AlertDescription>
        </Alert>
      )}

      <Section title="Geschäft">
        <Facts rows={details} />
      </Section>

      {paragraphs.length > 0 && (
        <Section title="Text">
          <div lang={language} className="flex max-w-[68ch] flex-col gap-4">
            {paragraphs.map((paragraph) => (
              <p
                key={paragraph}
                className="font-reading text-base leading-relaxed"
              >
                {paragraph}
              </p>
            ))}
            <p className="text-sm text-muted-foreground">
              Originalsprache: {LANGUAGE_NAME[language] ?? language}
            </p>
          </div>
        </Section>
      )}

      {record && record.n_docs > 0 && (
        <Section title="Dokumente">
          <Documents key={record.id} record={record} />
        </Section>
      )}

      <Section title="Gebiet">
        <Facts rows={area} />
      </Section>

      <Related key={affair.affair_id} affairId={affair.affair_id} link={link} />
    </div>
  )
}
