import { useEffect, useState } from "react"
import { Link } from "react-router"

import { Confidence } from "@/components/confidence"
import { ProcessingBadge } from "@/components/job-summary"
import { ReviewerName } from "@/components/reviewer-name"
import { PlainHeader, SortHeader } from "@/components/sort-header"
import { Button } from "@/components/ui/button"
import { compareValues, useSort, type SortDir } from "@/hooks/use-sort"
import { useReview } from "@/hooks/use-review"
import { useReviewQueue } from "@/hooks/use-review-queue"
import type { ReviewReason, ReviewSummary } from "@/lib/api"
import { reasonText } from "@/lib/label-state"
import { loadQueue, type ReviewCandidate } from "@/lib/review-queue"

const ALL = "alle"
const PAGE_SIZE = 25

type ReasonFilter = "alle" | "beleg" | "konfidenz"

// Jeder Grund ist ein Filter der API: GET /v1/reviews/queue?reason=…, mehrfach möglich.
const REASON_OPTIONS: {
  value: ReasonFilter
  label: string
  codes: ReviewReason[]
}[] = [
  { value: "alle", label: "Alle", codes: [] },
  {
    value: "beleg",
    label: "Beleg nicht im Text",
    codes: ["no_evidence", "evidence_unverified"],
  },
  { value: "konfidenz", label: "Konfidenz tief", codes: ["low_confidence"] },
]

interface Option {
  value: string
  label: string
  count: number
}

/** Parlamente mit gleichem Namen (Kanton und Stadt Zürich) tragen ihren Schlüssel dazu. */
function bodyOptions(rows: ReviewSummary["by_body"]): Option[] {
  const names = new Map<string, number>()
  for (const row of rows) {
    const name = row.name ?? row.body_key
    names.set(name, (names.get(name) ?? 0) + 1)
  }
  return rows.map((row) => {
    const name = row.name ?? row.body_key
    return {
      value: row.body_key,
      label: (names.get(name) ?? 0) > 1 ? `${name} · ${row.body_key}` : name,
      count: row.count,
    }
  })
}

interface Lists {
  query: string
  open: ReviewCandidate[]
  done: ReviewCandidate[]
  error: string | undefined
}

/** Offene und erledigte Labels zu den Filtern in `query`, auf dem Server gefiltert. */
function useLists(query: string, version: number): Lists | null {
  const [lists, setLists] = useState<Lists | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      loadQueue("open", query, controller.signal),
      loadQueue("done", query, controller.signal),
    ]).then(
      ([open, done]) => setLists({ query, open, done, error: undefined }),
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setLists({
            query,
            open: [],
            done: [],
            error: error instanceof Error ? error.message : String(error),
          })
        }
      }
    )
    return () => controller.abort()
  }, [query, version])
  return lists
}

type OpenKey = "affair" | "label" | "confidence"
type DoneKey = "affair" | "label" | "confidence" | "date"

function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("de-CH")
}

function sortValue(row: ReviewCandidate, key: DoneKey): string | number {
  switch (key) {
    case "affair":
      return row.title
    case "label":
      return row.labelName
    case "confidence":
      return row.confidence
    case "date":
      return row.decidedAt ?? ""
  }
}

function sortRows(
  rows: ReviewCandidate[],
  key: DoneKey,
  dir: SortDir
): ReviewCandidate[] {
  return [...rows].sort((a, b) =>
    compareValues(sortValue(a, key), sortValue(b, key), dir)
  )
}

function EvidenceLine({ row }: { row: ReviewCandidate }) {
  if (row.evidence === null) {
    return (
      <p className="mt-1 text-xs text-muted-foreground">Kein Beleg angegeben</p>
    )
  }
  const text =
    row.evidence.length > 220 ? `${row.evidence.slice(0, 220)} …` : row.evidence
  return (
    <p
      className="mt-1 line-clamp-2 text-xs text-muted-foreground"
      title={row.evidence}
    >
      Beleg:{" "}
      <span
        className={
          row.evidenceVerified ? "bg-evidence px-0.5 text-foreground" : "italic"
        }
      >
        «{text}»
      </span>
    </p>
  )
}

function AffairCell({
  row,
  evidence = false,
}: {
  row: ReviewCandidate
  evidence?: boolean
}) {
  return (
    <td className="max-w-[22rem] px-3 py-3">
      <p className="tabular text-xs text-muted-foreground">
        {[row.number, row.body].filter(Boolean).join(" · ")}
      </p>
      <Link
        to={`/admin/review/geschaefte/${row.affairId}`}
        title={row.title}
        className="line-clamp-2 text-base leading-snug font-medium underline-offset-4 hover:underline"
      >
        {row.title}
      </Link>
      {evidence && <EvidenceLine row={row} />}
    </td>
  )
}

function OpenTable({
  rows,
  threshold,
}: {
  rows: ReviewCandidate[]
  threshold: number
}) {
  const sort = useSort<OpenKey>("confidence", "asc")
  const [shown, setShown] = useState(PAGE_SIZE)
  const sorted = sortRows(rows, sort.key, sort.dir)
  const visible = sorted.slice(0, shown)
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[38rem] table-fixed border-collapse text-sm">
        <caption className="sr-only">Labels mit Prüfbedarf</caption>
        <colgroup>
          <col style={{ width: "42%" }} />
          <col style={{ width: "22%" }} />
          <col style={{ width: "12%" }} />
          <col style={{ width: "24%" }} />
        </colgroup>
        <thead className="border-b border-border bg-margin-tint">
          <tr>
            <SortHeader
              label="Geschäft"
              active={sort.key === "affair"}
              dir={sort.dir}
              onSort={() => sort.sortBy("affair", "asc")}
            />
            <SortHeader
              label="Label"
              active={sort.key === "label"}
              dir={sort.dir}
              onSort={() => sort.sortBy("label", "asc")}
            />
            <SortHeader
              label="Konfidenz"
              active={sort.key === "confidence"}
              dir={sort.dir}
              onSort={() => sort.sortBy("confidence", "asc")}
            />
            <PlainHeader>Grund</PlainHeader>
          </tr>
        </thead>
        <tbody>
          {visible.map((row) => (
            <tr
              key={`${row.affairId}|${row.tagId}`}
              className="border-b border-border align-top"
            >
              <AffairCell row={row} evidence />
              <td className="px-3 py-3">{row.labelName}</td>
              <td className="px-3 py-3 whitespace-nowrap">
                <Confidence value={row.confidence} />
              </td>
              <td className="px-3 py-3 text-xs">
                {row.reasons
                  .map((reason) => reasonText(reason, threshold))
                  .join(", ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {sorted.length > visible.length && (
        <div className="flex items-center gap-3 px-3 py-3 text-xs text-muted-foreground">
          <span className="tabular">
            {visible.length} von {sorted.length} angezeigt
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
    </div>
  )
}

function FilterSelect({
  label,
  value,
  onChange,
  allLabel,
  options,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  allLabel: string
  options: Option[]
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-8 w-44 truncate rounded-md border border-input bg-background px-2 text-xs text-foreground"
    >
      <option value={ALL}>{allLabel}</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label} ({option.count})
        </option>
      ))}
    </select>
  )
}

function Progress({ done, total }: { done: number; total: number }) {
  const share = total === 0 ? 0 : Math.round((done / total) * 100)
  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground">
      <div
        role="progressbar"
        aria-label="Fortschritt des Reviews"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={done}
        className="h-1 w-24 bg-border"
      >
        <div className="h-full bg-chart-1" style={{ width: `${share}%` }} />
      </div>
      <span>
        <span className="tabular font-medium text-foreground">
          {done} von {total}
        </span>{" "}
        entschieden
      </span>
    </div>
  )
}

const DECISION_NAME = {
  confirmed: "Bestätigt",
  rejected: "Verworfen",
  changed: "Geändert",
} as const

function DoneTable({ rows }: { rows: ReviewCandidate[] }) {
  const review = useReview()
  const [pending, setPending] = useState<string>()
  const [error, setError] = useState<string>()

  async function undo(row: ReviewCandidate) {
    const key = `${row.affairId}|${row.tagId}`
    setPending(key)
    setError(undefined)
    try {
      await review.decide(row.affairId, row.tagId, "undo")
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    } finally {
      setPending(undefined)
    }
  }

  const sort = useSort<DoneKey>("date", "desc")
  const sorted = sortRows(rows, sort.key, sort.dir)
  return (
    <div className="overflow-x-auto">
      {error && (
        <p role="alert" className="pb-2 text-sm text-destructive">
          Rückgängig nicht gespeichert: {error}
        </p>
      )}
      <table className="w-full min-w-[38rem] table-fixed border-collapse text-sm">
        <caption className="sr-only">Entschiedene Labels</caption>
        <colgroup>
          <col style={{ width: "42%" }} />
          <col style={{ width: "22%" }} />
          <col style={{ width: "12%" }} />
          <col style={{ width: "24%" }} />
        </colgroup>
        <thead className="border-b border-border bg-margin-tint">
          <tr>
            <SortHeader
              label="Geschäft"
              active={sort.key === "affair"}
              dir={sort.dir}
              onSort={() => sort.sortBy("affair", "asc")}
            />
            <SortHeader
              label="Label"
              active={sort.key === "label"}
              dir={sort.dir}
              onSort={() => sort.sortBy("label", "asc")}
            />
            <SortHeader
              label="Konfidenz"
              active={sort.key === "confidence"}
              dir={sort.dir}
              onSort={() => sort.sortBy("confidence", "desc")}
            />
            <SortHeader
              label="Entscheid"
              active={sort.key === "date"}
              dir={sort.dir}
              onSort={() => sort.sortBy("date", "desc")}
            />
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const key = `${row.affairId}|${row.tagId}|${row.decidedAt}`
            return (
              <tr key={key} className="border-b border-border align-top">
                <AffairCell row={row} />
                <td className="px-3 py-3">{row.labelName}</td>
                <td className="px-3 py-3 whitespace-nowrap">
                  <Confidence value={row.confidence} />
                </td>
                <td className="px-3 py-3 text-xs">
                  <span className="font-semibold">
                    {DECISION_NAME[row.decision ?? "confirmed"]}
                  </span>{" "}
                  von {row.decidedBy}
                  <span className="tabular block text-muted-foreground">
                    {row.decidedAt ? formatDate(row.decidedAt) : ""}
                  </span>
                  {review.active && (
                    <div className="mt-2">
                      <Button
                        size="xs"
                        variant="outline"
                        disabled={pending === `${row.affairId}|${row.tagId}`}
                        onClick={() => undo(row)}
                      >
                        Rückgängig
                      </Button>
                    </div>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// Arbeitsliste: Labels mit Prüfbedarf, standardmässig die unsichersten zuerst. Entschiedene
// stehen getrennt, eingeklappt, damit die Liste oben nur zeigt, was noch zu tun ist. Gefiltert
// wird auf dem Server; die Zahlen in den Filtern liefert GET /v1/reviews/summary.
export function ReviewPage() {
  const [reason, setReason] = useState<ReasonFilter>("alle")
  const [area, setArea] = useState(ALL)
  const [body, setBody] = useState(ALL)
  const [topic, setTopic] = useState(ALL)
  const live = useReviewQueue()
  const params = new URLSearchParams()
  const codes = REASON_OPTIONS.find((option) => option.value === reason)?.codes
  for (const code of codes ?? []) params.append("reason", code)
  const page = topic !== ALL ? topic : area
  if (page !== ALL) params.set("page_id", page)
  if (body !== ALL) params.set("body_key", body)
  const query = params.toString()
  const lists = useLists(query, live.version)
  // Ein neuer Filter lädt; bis dahin bleibt die alte Liste blass stehen.
  const busy = lists !== null && lists.query !== query
  const error = lists?.error ?? live.error
  const open = lists?.open ?? []
  const done = lists?.done ?? []
  const summary = live.summary
  const total = summary ? summary.open + summary.done : 0
  const areas = (summary?.by_area ?? []).map((row) => ({
    value: row.page_id,
    label: row.title,
    count: row.count,
  }))
  const bodies = bodyOptions(summary?.by_body ?? [])
  // Themen des Bereichs: APS-IDs beginnen mit ihm (aps:6.1.9 liegt in aps:6), wie in der API.
  const topics = (summary?.by_topic ?? [])
    .filter((row) => row.tag_id.startsWith(`${area}.`))
    .map((row) => ({ value: row.tag_id, label: row.name_de, count: row.count }))
  const filtered =
    reason !== "alle" || area !== ALL || body !== ALL || topic !== ALL
  const reset = () => {
    setReason("alle")
    setArea(ALL)
    setBody(ALL)
    setTopic(ALL)
  }

  return (
    <>
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
            Review
          </h1>
          <ProcessingBadge />
        </div>
        <p className="max-w-[68ch] text-muted-foreground">
          Labels sind Vorschläge. Hier stehen die unsichersten zuerst: niedrige
          Konfidenz oder ein Beleg, der nicht im Text steht. Öffne das Geschäft,
          lies den Beleg und entscheide.
        </p>
        <div className="pt-2">
          <ReviewerName />
        </div>
      </div>
      <section
        aria-labelledby="queue-heading"
        className="flex flex-col gap-3 pt-2"
      >
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <h2 id="queue-heading" className="font-heading text-lg font-medium">
            Offen ({open.length})
          </h2>
          <Progress done={summary?.done ?? 0} total={total} />
        </div>
        {total > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <div
              role="group"
              aria-label="Grund"
              className="inline-flex overflow-hidden rounded-md border border-border text-xs"
            >
              {REASON_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={reason === option.value}
                  onClick={() => setReason(option.value)}
                  className={
                    reason === option.value
                      ? "h-8 bg-secondary px-3 font-medium text-foreground"
                      : "h-8 bg-background px-3 text-muted-foreground hover:bg-muted hover:text-foreground"
                  }
                >
                  {option.label}
                </button>
              ))}
            </div>
            {areas.length > 1 && (
              <FilterSelect
                label="Bereich"
                value={area}
                onChange={(value) => {
                  setArea(value)
                  setTopic(ALL)
                }}
                allLabel="Alle Bereiche"
                options={areas}
              />
            )}
            {area !== ALL && topics.length > 1 && (
              <FilterSelect
                label="Thema"
                value={topic}
                onChange={setTopic}
                allLabel="Alle Themen des Bereichs"
                options={topics}
              />
            )}
            {bodies.length > 1 && (
              <FilterSelect
                label="Körperschaft"
                value={body}
                onChange={setBody}
                allLabel="Alle Körperschaften"
                options={bodies}
              />
            )}
            {filtered && (
              <Button size="sm" variant="ghost" onClick={reset}>
                Filter zurücksetzen
              </Button>
            )}
          </div>
        )}
        {lists === null && (
          <p className="text-muted-foreground">Labels werden geladen …</p>
        )}
        {error && (
          <p className="text-sm text-destructive">
            Labels nicht geladen: {error}
          </p>
        )}
        {lists === null || error ? null : open.length > 0 ? (
          <div aria-busy={busy} className={busy ? "opacity-50" : undefined}>
            <OpenTable
              key={lists.query}
              rows={open}
              threshold={live.threshold ?? 0}
            />
          </div>
        ) : (
          <p className="text-muted-foreground">
            {filtered
              ? "Kein offenes Label passt zu diesen Filtern."
              : done.length > 0
                ? "Alles geprüft."
                : "Nichts zu prüfen."}
          </p>
        )}
      </section>
      {done.length > 0 && (
        <details className="pt-4">
          <summary className="cursor-pointer font-heading text-lg font-medium underline-offset-4 hover:underline">
            Erledigt ({done.length})
          </summary>
          <div className="mt-3">
            <DoneTable rows={done} />
          </div>
        </details>
      )}
    </>
  )
}
