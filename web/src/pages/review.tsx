import { useState } from "react"
import { Link } from "react-router"

import { Confidence } from "@/components/confidence"
import { ProcessingBadge } from "@/components/job-summary"
import { ReviewerName } from "@/components/reviewer-name"
import { PlainHeader, SortHeader } from "@/components/sort-header"
import { Button } from "@/components/ui/button"
import { compareValues, useSort, type SortDir } from "@/hooks/use-sort"
import { useReview } from "@/hooks/use-review"
import { reviewKey } from "@/lib/review"
import { useReviewQueue } from "@/hooks/use-review-queue"
import { buildQueue, type QueueRow } from "@/lib/review-queue"

const ALL = "alle"
const PAGE_SIZE = 25

type ReasonFilter = "alle" | "beleg" | "konfidenz"

const REASON_OPTIONS: { value: ReasonFilter; label: string }[] = [
  { value: "alle", label: "Alle" },
  { value: "beleg", label: "Beleg nicht im Text" },
  { value: "konfidenz", label: "Konfidenz tief" },
]

function matchesReason(row: QueueRow, filter: ReasonFilter): boolean {
  if (filter === "alle") return true
  const key = filter === "beleg" ? "Beleg" : "Konfidenz"
  return row.reasons.some((reason) => reason.includes(key))
}

function countBy(rows: QueueRow[], pick: (row: QueueRow) => string | null) {
  const counts = new Map<string, number>()
  for (const row of rows) {
    const key = pick(row)
    if (key) counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0], "de"))
}

type OpenKey = "affair" | "label" | "confidence"
type DoneKey = "affair" | "label" | "confidence" | "date"

function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("de-CH")
}

function sortValue(row: QueueRow, key: DoneKey): string | number {
  switch (key) {
    case "affair":
      return row.title
    case "label":
      return row.labelName
    case "confidence":
      return row.confidence
    case "date":
      return row.entry?.at ?? ""
  }
}

function sortRows(rows: QueueRow[], key: DoneKey, dir: SortDir): QueueRow[] {
  return [...rows].sort((a, b) =>
    compareValues(sortValue(a, key), sortValue(b, key), dir)
  )
}

function EvidenceLine({ row }: { row: QueueRow }) {
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
  row: QueueRow
  evidence?: boolean
}) {
  return (
    <td className="max-w-[22rem] px-3 py-3">
      <p className="tabular text-xs text-muted-foreground">
        {[row.number, row.body].filter(Boolean).join(" · ")}
      </p>
      <Link
        to={`/review/geschaefte/${row.affairId}`}
        title={row.title}
        className="line-clamp-2 text-base leading-snug font-medium underline-offset-4 hover:underline"
      >
        {row.title}
      </Link>
      {evidence && <EvidenceLine row={row} />}
    </td>
  )
}

function OpenTable({ rows }: { rows: QueueRow[] }) {
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
              <td className="px-3 py-3 text-xs">{row.reasons.join(", ")}</td>
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
  options: [string, number][]
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-8 w-44 truncate rounded-md border border-input bg-background px-2 text-xs text-foreground"
    >
      <option value={ALL}>{allLabel}</option>
      {options.map(([name, count]) => (
        <option key={name} value={name}>
          {name} ({count})
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
        <div className="h-full bg-primary" style={{ width: `${share}%` }} />
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

function DoneTable({ rows }: { rows: QueueRow[] }) {
  const review = useReview()
  const sort = useSort<DoneKey>("date", "desc")
  const sorted = sortRows(rows, sort.key, sort.dir)
  return (
    <div className="overflow-x-auto">
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
            const entry = row.entry
            if (!entry) return null
            const key = reviewKey(row.affairId, row.tagId)
            return (
              <tr key={key} className="border-b border-border align-top">
                <AffairCell row={row} />
                <td className="px-3 py-3">{row.labelName}</td>
                <td className="px-3 py-3 whitespace-nowrap">
                  <Confidence value={row.confidence} />
                </td>
                <td className="px-3 py-3 text-xs">
                  <span className="font-semibold">
                    {entry.decision === "confirmed" ? "Bestätigt" : "Verworfen"}
                  </span>{" "}
                  von {entry.by}
                  <span className="tabular block text-muted-foreground">
                    {formatDate(entry.at)}
                  </span>
                  {review.active && (
                    <div className="mt-2">
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => review.undo(key)}
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
// stehen getrennt, eingeklappt, damit die Liste oben nur zeigt, was noch zu tun ist.
export function ReviewPage() {
  const review = useReview()
  const [reason, setReason] = useState<ReasonFilter>("alle")
  const [area, setArea] = useState(ALL)
  const [body, setBody] = useState(ALL)
  const [topic, setTopic] = useState(ALL)
  const live = useReviewQueue()
  const queue = buildQueue(live.candidates, review.decisions)
  const rows = queue.filter(
    (row) =>
      matchesReason(row, reason) &&
      (area === ALL || row.areaName === area) &&
      (body === ALL || row.body === body) &&
      (topic === ALL || row.labelName === topic)
  )
  const open = rows.filter((row) => !row.entry)
  const done = rows.filter((row) => row.entry)
  const openAll = queue.filter((row) => !row.entry)
  const areas = countBy(openAll, (row) => row.areaName)
  const bodies = countBy(openAll, (row) => row.body)
  const topics = countBy(
    openAll.filter((row) => area === ALL || row.areaName === area),
    (row) => row.labelName
  )
  const filtered =
    reason !== "alle" || area !== ALL || body !== ALL || topic !== ALL
  const reset = () => {
    setReason("alle")
    setArea(ALL)
    setBody(ALL)
    setTopic(ALL)
  }

  if (!review.active) {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
            Review
          </h1>
          <ProcessingBadge />
        </div>
        <p className="max-w-[68ch] text-muted-foreground">
          Der Review ist für Mitarbeitende, die Labels prüfen. Wähle oben rechts
          die Ansicht «Admin», um die Warteschlange zu sehen und Labels zu
          bestätigen oder zu verwerfen.
        </p>
      </div>
    )
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
        <p className="text-xs text-muted-foreground">
          Echte Labels aus der API. Entscheide gelten vorerst nur in diesem
          Browser; zum Speichern fehlt noch der Endpunkt im Backend.
        </p>
      </div>
      <section
        aria-labelledby="queue-heading"
        className="flex flex-col gap-3 pt-2"
      >
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <h2 id="queue-heading" className="font-heading text-lg font-medium">
            Offen ({open.length})
          </h2>
          <Progress
            done={queue.filter((row) => row.entry).length}
            total={queue.length}
          />
        </div>
        {queue.length > 0 && (
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
        {live.loading && (
          <p className="text-muted-foreground">Labels werden geladen …</p>
        )}
        {live.error && (
          <p className="text-sm text-destructive">
            Labels nicht geladen: {live.error}
          </p>
        )}
        {live.loading || live.error ? null : open.length > 0 ? (
          <OpenTable
            key={`${reason}|${area}|${body}|${topic}`}
            rows={open}
          />
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
