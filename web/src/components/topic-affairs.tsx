import { useMemo, useState } from "react"

import { AffairTable } from "@/components/affair-table"
import { Distribution, type DistributionRow } from "@/components/distribution"
import { Segmented } from "@/components/segmented"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useAllAffairs } from "@/hooks/use-all-affairs"
import type { TopicAffair, WikiPage } from "@/lib/api"
import { affairsToCsv, downloadText, LEVEL_LABEL } from "@/lib/export"
import { useReviewQueue } from "@/hooks/use-review-queue"

const PAGE_SIZE = 50
const TOP_BODIES = 8
const LEVELS = ["country", "canton", "city", "municipality"]

type ConfidenceFilter = "alle" | "mittel"

interface Filters {
  level: string | null
  body: string | null
  year: string | null
  confidence: ConfidenceFilter
}

const NO_FILTER: Filters = {
  level: null,
  body: null,
  year: null,
  confidence: "alle",
}

function yearOf(row: TopicAffair): string {
  return row.begin_date ? row.begin_date.slice(0, 4) : "ohne Datum"
}

/** Wendet die Filter an; `skip` lässt einen aus, damit seine Verteilung die Alternativen zeigt. */
function apply(
  rows: TopicAffair[],
  filters: Filters,
  minConfidence: number,
  skip?: keyof Filters
): TopicAffair[] {
  return rows.filter(
    (row) =>
      (skip === "level" ||
        filters.level === null ||
        row.body_level === filters.level) &&
      (skip === "body" ||
        filters.body === null ||
        row.body_key === filters.body) &&
      (skip === "year" ||
        filters.year === null ||
        yearOf(row) === filters.year) &&
      (skip === "confidence" ||
        filters.confidence === "alle" ||
        row.confidence >= minConfidence)
  )
}

function countRows(
  rows: TopicAffair[],
  key: (row: TopicAffair) => string | null,
  label: (key: string, row: TopicAffair) => string
): DistributionRow[] {
  const counts = new Map<string, DistributionRow>()
  for (const row of rows) {
    const k = key(row)
    if (k === null) continue
    const entry = counts.get(k) ?? { key: k, label: label(k, row), count: 0 }
    entry.count += 1
    counts.set(k, entry)
  }
  return [...counts.values()]
}

// Auswertung und Geschäftsliste einer Themenseite. Bereiche, Kapitel und die Wurzel tragen selbst
// keine Labels und zeigen deshalb keinen Abschnitt. Die Daten kommen seitenweise aus
// GET /v1/pages/{id}/affairs, die Auswertung rechnet im Browser; die Auswahl in den Verteilungen
// filtert Kennzahlen, Liste und Export gemeinsam.
export function TopicAffairs({ page }: { page: WikiPage }) {
  if (page.kind !== "tag" && page.kind !== "querschnitt") return null
  return <TopicOverview key={page.page_id} pageId={page.page_id} />
}

function TopicOverview({ pageId }: { pageId: string }) {
  const all = useAllAffairs(pageId)
  // Schwelle der Klassifikation aus der API; bis sie da ist, gilt der Startwert.
  const minConfidence = useReviewQueue().threshold ?? 0.6
  const [filters, setFilters] = useState<Filters>(NO_FILTER)
  const set = (patch: Partial<Filters>) =>
    setFilters((current) => ({ ...current, ...patch }))

  const rows = useMemo(
    () => apply(all.items, filters, minConfidence),
    [all.items, filters, minConfidence]
  )
  const levels = useMemo(
    () =>
      countRows(
        apply(all.items, filters, minConfidence, "level"),
        (row) => row.body_level,
        (key) => LEVEL_LABEL[key] ?? key
      ).sort((a, b) => LEVELS.indexOf(a.key) - LEVELS.indexOf(b.key)),
    [all.items, filters, minConfidence]
  )
  const bodiesAll = useMemo(() => {
    const rows = countRows(
      apply(all.items, filters, minConfidence, "body"),
      (row) => row.body_key,
      (_, row) => row.body_name ?? row.body_key
    )
    // Gleich benannte Parlamente (Kanton und Stadt Zürich) mit der Ebene unterscheiden.
    const levelOf = new Map(all.items.map((row) => [row.body_key, row.body_level]))
    const names = new Map<string, number>()
    for (const row of rows) names.set(row.label, (names.get(row.label) ?? 0) + 1)
    return rows
      .map((row) => {
        const level = levelOf.get(row.key)
        return (names.get(row.label) ?? 0) > 1 && level
          ? { ...row, label: `${row.label} (${LEVEL_LABEL[level] ?? level})` }
          : row
      })
      .sort((a, b) => b.count - a.count)
  }, [all.items, filters, minConfidence])
  const years = useMemo(
    () =>
      countRows(apply(all.items, filters, minConfidence, "year"), yearOf, (key) => key).sort(
        (a, b) => a.key.localeCompare(b.key)
      ),
    [all.items, filters, minConfidence]
  )
  const bodies = bodiesAll.slice(0, TOP_BODIES)
  const active =
    filters.level !== null ||
    filters.body !== null ||
    filters.year !== null ||
    filters.confidence !== "alle"

  if (all.loading) {
    return (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }
  if (all.error) {
    return (
      <p className="text-sm text-destructive">
        Geschäfte nicht geladen: {all.error}
      </p>
    )
  }
  if (all.total === 0) {
    return (
      <section aria-labelledby="affairs-heading" className="flex flex-col gap-2">
        <h2 id="affairs-heading" className="font-heading text-lg font-medium">
          Geschäfte (0)
        </h2>
        <p className="text-muted-foreground">
          Noch keine Geschäfte mit diesem Thema.
        </p>
      </section>
    )
  }

  const bodyCount = new Set(rows.map((row) => row.body_key)).size
  const dates = rows.flatMap((row) => (row.begin_date ? [row.begin_date] : []))
  const first = dates.length ? dates.reduce((a, b) => (a < b ? a : b)) : ""
  const last = dates.length ? dates.reduce((a, b) => (a > b ? a : b)) : ""
  const verified = rows.filter((row) => row.evidence_verified).length
  const share = rows.length === 0 ? 0 : Math.round((verified / rows.length) * 100)
  const slug = pageId.replace(/[^a-z0-9]+/gi, "-")

  return (
    <>
      <section aria-labelledby="overview-heading" className="flex flex-col gap-4">
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

        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          <div>
            <dt className="text-xs text-muted-foreground">Geschäfte</dt>
            <dd className="tabular text-2xl font-semibold">{rows.length}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Parlamente</dt>
            <dd className="tabular text-2xl font-semibold">{bodyCount}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Zeitraum</dt>
            <dd className="tabular text-2xl font-semibold">
              {first ? first.slice(0, 4) : "–"}
              {last && last.slice(0, 4) !== first.slice(0, 4)
                ? `–${last.slice(0, 4)}`
                : ""}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">
              Beleg im Text gefunden
            </dt>
            <dd className="tabular text-2xl font-semibold">{share} %</dd>
          </div>
        </dl>

        <div className="grid gap-x-8 gap-y-5 md:grid-cols-3">
          <Distribution
            title="Nach Ebene"
            rows={levels}
            activeKey={filters.level}
            onPick={(level) => set({ level })}
          />
          <Distribution
            title="Nach Parlament"
            rows={bodies}
            activeKey={filters.body}
            onPick={(body) => set({ body })}
            note={
              bodiesAll.length > TOP_BODIES
                ? `und ${bodiesAll.length - TOP_BODIES} weitere Parlamente`
                : undefined
            }
          />
          <Distribution
            title="Nach Jahr"
            rows={years}
            activeKey={filters.year}
            onPick={(year) => set({ year })}
          />
        </div>

        {all.total > all.items.length && (
          <p className="text-xs text-muted-foreground">
            Ausgewertet sind die ersten {all.items.length} von {all.total}{" "}
            Geschäften. Alle stehen in der API.
          </p>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Button
            size="sm"
            variant="outline"
            disabled={rows.length === 0}
            onClick={() =>
              downloadText(
                `parltopics-${slug}-${new Date().toISOString().slice(0, 10)}.csv`,
                affairsToCsv(rows)
              )
            }
          >
            Als CSV herunterladen ({rows.length})
          </Button>
          <span className="text-xs text-muted-foreground">
            Für Excel (Semikolon), mit Konfidenz und Beleg je Geschäft.
          </span>
        </div>
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer py-1 underline-offset-2 hover:underline">
            API-Abfrage für diese Daten
          </summary>
          <p className="pt-1">
            <code className="break-all text-foreground">
              GET /v1/pages/{pageId}/affairs?limit=500
            </code>
          </p>
          <p>
            Filter: <code>level</code> (country, canton, city, municipality),{" "}
            <code>body_key</code>, <code>type</code>, <code>from</code>,{" "}
            <code>to</code>, <code>min_confidence</code>, <code>offset</code>.
          </p>
        </details>
      </section>

      <AffairList
        key={`${filters.level}|${filters.body}|${filters.year}|${filters.confidence}`}
        rows={rows}
      />
    </>
  )
}

function AffairList({ rows }: { rows: TopicAffair[] }) {
  const [shown, setShown] = useState(PAGE_SIZE)
  return (
    <section aria-labelledby="affairs-heading" className="flex flex-col gap-2">
      <h2 id="affairs-heading" className="font-heading text-lg font-medium">
        Geschäfte ({rows.length})
      </h2>
      {rows.length === 0 ? (
        <p className="text-muted-foreground">
          Kein Geschäft passt zu diesen Filtern.
        </p>
      ) : (
        <>
          <AffairTable rows={rows.slice(0, shown)} />
          {rows.length > shown && (
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="tabular">
                {shown} von {rows.length} angezeigt
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShown((count) => count + PAGE_SIZE)}
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
