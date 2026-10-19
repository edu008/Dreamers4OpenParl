import { cn } from "cn"
import { useState } from "react"

import { AffairTable } from "@/components/affair-table"
import { Distribution, type DistributionRow } from "@/components/distribution"
import { Segmented } from "@/components/segmented"
import { Button, buttonVariants } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import { useReviewQueue } from "@/hooks/use-review-queue"
import {
  fetchJson,
  type AffairsSummary,
  type TopicAffair,
  type TopicAffairs,
  type WikiPage,
} from "@/lib/api"
import { LEVEL_LABEL } from "@/lib/export"

const PAGE_SIZE = 50
const TOP_BODIES = 8

type ConfidenceFilter = "alle" | "mittel"

interface Filters {
  level: string | null
  body: string | null
  year: string | null
  type: string | null
  confidence: ConfidenceFilter
}

const NO_FILTER: Filters = {
  level: null,
  body: null,
  year: null,
  type: null,
  confidence: "alle",
}

/** Filter als Abfrage der Seiten-Endpunkte; ein Jahr wird zu from und to. */
function filterQuery(filters: Filters, minConfidence: number): string {
  const params = new URLSearchParams()
  if (filters.level) params.set("level", filters.level)
  if (filters.body) params.set("body_key", filters.body)
  if (filters.type) params.set("type", filters.type)
  if (filters.year) {
    params.set("from", `${filters.year}-01-01`)
    params.set("to", `${filters.year}-12-31`)
  }
  if (filters.confidence === "mittel") {
    params.set("min_confidence", String(minConfidence))
  }
  return params.toString()
}

function withQuery(path: string, query: string): string {
  return query ? `${path}?${query}` : path
}

// Auswertung und Geschäftsliste einer Themenseite. Bereiche, Kapitel und die Wurzel tragen selbst
// keine Labels und zeigen deshalb keinen Abschnitt. Kennzahlen und Verteilungen rechnet
// GET /v1/pages/{id}/affairs/summary über alle Geschäfte, die Liste kommt seitenweise aus /affairs
// und der Export aus /affairs.csv; die Auswahl in den Verteilungen filtert alle drei.
export function TopicAffairs({ page }: { page: WikiPage }) {
  if (page.kind !== "tag" && page.kind !== "querschnitt") return null
  return <TopicOverview key={page.page_id} pageId={page.page_id} />
}

function TopicOverview({ pageId }: { pageId: string }) {
  // Schwelle der Klassifikation aus der API; bis sie da ist, gilt der Startwert.
  const minConfidence = useReviewQueue().threshold ?? 0.6
  const [filters, setFilters] = useState<Filters>(NO_FILTER)
  const set = (patch: Partial<Filters>) =>
    setFilters((current) => ({ ...current, ...patch }))
  const base = `/v1/pages/${encodeURIComponent(pageId)}/affairs`
  const query = filterQuery(filters, minConfidence)
  const summaryPath = withQuery(`${base}/summary`, query)
  const csvPath = withQuery(`${base}.csv`, query)
  const summary = useApi<AffairsSummary>(summaryPath)
  // Beim Filtern bleibt die alte Auswertung stehen, bis die neue da ist; so bleibt der Fokus.
  const data = summary.data ?? summary.last
  const active =
    filters.level !== null ||
    filters.body !== null ||
    filters.year !== null ||
    filters.type !== null ||
    filters.confidence !== "alle"

  if (!data) {
    return summary.error ? (
      <p className="text-sm text-destructive">
        Geschäfte nicht geladen: {summary.error}
      </p>
    ) : (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }
  if (summary.data?.rows === 0 && !active) {
    return (
      <section
        aria-labelledby="affairs-heading"
        className="flex flex-col gap-2"
      >
        <h2 id="affairs-heading" className="font-heading text-lg font-medium">
          Geschäfte (0)
        </h2>
        <p className="text-muted-foreground">
          Noch keine Geschäfte mit diesem Thema.
        </p>
      </section>
    )
  }

  const levels: DistributionRow[] = data.by_level.flatMap((row) =>
    row.level
      ? [
          {
            key: row.level,
            label: LEVEL_LABEL[row.level] ?? row.level,
            count: row.count,
          },
        ]
      : []
  )
  // Gleich benannte Parlamente (Kanton und Stadt Zürich) mit der Ebene unterscheiden.
  const names = new Map<string, number>()
  for (const row of data.by_body) {
    const name = row.name ?? row.body_key
    names.set(name, (names.get(name) ?? 0) + 1)
  }
  const bodies: DistributionRow[] = data.by_body.map((row) => {
    const name = row.name ?? row.body_key
    return {
      key: row.body_key,
      label:
        (names.get(name) ?? 0) > 1 && row.level
          ? `${name} (${LEVEL_LABEL[row.level] ?? row.level})`
          : name,
      count: row.count,
    }
  })
  // Ohne Datum oder Typ lässt sich nicht filtern; die Zahl steht unter der Verteilung.
  const years: DistributionRow[] = data.by_year.flatMap((row) =>
    row.year === null
      ? []
      : [{ key: String(row.year), label: String(row.year), count: row.count }]
  )
  const undated = data.by_year.find((row) => row.year === null)?.count ?? 0
  const types: DistributionRow[] = data.by_type.flatMap((row) =>
    row.type === null
      ? []
      : [{ key: row.type, label: row.type_de ?? row.type, count: row.count }]
  )
  const untyped = data.by_type.find((row) => row.type === null)?.count ?? 0
  const first = data.first_date?.slice(0, 4) ?? ""
  const last = data.last_date?.slice(0, 4) ?? ""
  const share =
    data.rows === 0 ? 0 : Math.round((data.verified / data.rows) * 100)

  return (
    <>
      <section
        aria-labelledby="overview-heading"
        aria-busy={summary.loading}
        className="flex flex-col gap-4"
      >
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h2
            id="overview-heading"
            className="font-heading text-lg font-medium"
          >
            Auswertung
          </h2>
          <Segmented<ConfidenceFilter>
            label="Konfidenz"
            options={[
              { value: "alle", label: "Alle Geschäfte" },
              { value: "mittel", label: `Ab Konfidenz ${minConfidence}` },
            ]}
            value={filters.confidence}
            onChange={(confidence) => set({ confidence })}
          />
          {active && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setFilters(NO_FILTER)}
            >
              Filter zurücksetzen
            </Button>
          )}
        </div>
        {summary.error && (
          <p role="alert" className="text-sm text-destructive">
            Auswertung nicht geladen: {summary.error}
          </p>
        )}

        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          <div>
            <dt className="text-xs text-muted-foreground">Geschäfte</dt>
            <dd className="tabular text-2xl font-semibold">{data.affairs}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Parlamente</dt>
            <dd className="tabular text-2xl font-semibold">{data.bodies}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Zeitraum</dt>
            <dd className="tabular text-2xl font-semibold">
              {first || "–"}
              {last && last !== first ? `–${last}` : ""}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">
              Beleg im Text gefunden
            </dt>
            <dd className="tabular text-2xl font-semibold">{share} %</dd>
          </div>
        </dl>

        <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
          <Distribution
            title="Nach Ebene"
            rows={levels}
            activeKey={filters.level}
            onPick={(level) => set({ level })}
          />
          <Distribution
            title="Nach Parlament"
            rows={bodies.slice(0, TOP_BODIES)}
            activeKey={filters.body}
            onPick={(body) => set({ body })}
            note={
              bodies.length > TOP_BODIES
                ? `und ${bodies.length - TOP_BODIES} weitere Parlamente`
                : undefined
            }
          />
          <Distribution
            title="Nach Jahr"
            rows={years}
            activeKey={filters.year}
            onPick={(year) => set({ year })}
            note={undated > 0 ? `und ${undated} ohne Datum` : undefined}
          />
          <Distribution
            title="Nach Typ"
            rows={types}
            activeKey={filters.type}
            onPick={(type) => set({ type })}
            note={untyped > 0 ? `und ${untyped} ohne Typ` : undefined}
          />
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <a
            href={data.rows > 0 ? csvPath : undefined}
            download
            aria-disabled={data.rows === 0}
            className={cn(
              buttonVariants({
                variant: "outline",
                size: "sm",
                className: "aria-disabled:opacity-50",
              })
            )}
          >
            Als CSV herunterladen ({data.rows})
          </a>
          <span className="text-xs text-muted-foreground">
            Für Excel (Semikolon), mit Konfidenz und Beleg je Geschäft.
          </span>
        </div>
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer py-1 underline-offset-2 hover:underline">
            API-Abfrage für diese Daten
          </summary>
          <p className="pt-1">
            <code className="break-all text-foreground">GET {summaryPath}</code>
          </p>
          <p>
            <code className="break-all text-foreground">GET {csvPath}</code>
          </p>
          <p>
            Filter: <code>level</code> (country, canton, city, municipality),{" "}
            <code>body_key</code>, <code>type</code>, <code>from</code>,{" "}
            <code>to</code>, <code>min_confidence</code>; die Liste unter{" "}
            <code>/affairs</code> mit <code>limit</code> und <code>offset</code>
            .
          </p>
        </details>
      </section>

      <AffairList key={query} base={base} query={query} />
    </>
  )
}

/** Eine Seite der Liste: die Filter aus `query` plus limit und offset. */
function pagePath(base: string, query: string, offset: number): string {
  const params = new URLSearchParams(query)
  params.set("limit", String(PAGE_SIZE))
  params.set("offset", String(offset))
  return `${base}?${params}`
}

function AffairList({ base, query }: { base: string; query: string }) {
  const first = useApi<TopicAffairs>(pagePath(base, query, 0))
  const [more, setMore] = useState<TopicAffair[]>([])
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string>()
  const rows = [...(first.data?.items ?? []), ...more]
  const total = first.data?.total ?? 0

  async function loadMore() {
    setLoadingMore(true)
    setError(undefined)
    try {
      const page = await fetchJson<TopicAffairs>(
        pagePath(base, query, rows.length)
      )
      setMore((current) => [...current, ...page.items])
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <section aria-labelledby="affairs-heading" className="flex flex-col gap-2">
      <h2 id="affairs-heading" className="font-heading text-lg font-medium">
        Geschäfte{first.data ? ` (${total})` : ""}
      </h2>
      {first.error ? (
        <p className="text-sm text-destructive">
          Geschäfte nicht geladen: {first.error}
        </p>
      ) : first.loading ? (
        <Skeleton className="h-32 w-full" />
      ) : rows.length === 0 ? (
        <p className="text-muted-foreground">
          Kein Geschäft passt zu diesen Filtern.
        </p>
      ) : (
        <>
          <AffairTable rows={rows} />
          {error && (
            <p role="alert" className="text-sm text-destructive">
              Weitere Geschäfte nicht geladen: {error}
            </p>
          )}
          {total > rows.length && (
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="tabular">
                {rows.length} von {total} angezeigt
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={loadingMore}
                onClick={loadMore}
              >
                Mehr anzeigen
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  )
}
