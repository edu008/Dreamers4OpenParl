import { useState } from "react"
import { Link } from "react-router"

import { Confidence } from "@/components/confidence"
import { JobTable, ProcessingBadge, SystemList } from "@/components/job-summary"
import { ReviewSignIn } from "@/components/review-signin"
import { PlainHeader, SortHeader } from "@/components/sort-header"
import { Button } from "@/components/ui/button"
import { compareValues, useSort, type SortDir } from "@/hooks/use-sort"
import { useReview } from "@/hooks/use-review"
import { reviewKey } from "@/lib/review"
import { useReviewQueue } from "@/hooks/use-review-queue"
import { buildQueue, type QueueRow } from "@/lib/review-queue"

const ALL = "alle"

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

function AffairCell({ row }: { row: QueueRow }) {
  return (
    <td className="max-w-[22rem] px-3 py-3">
      <p className="tabular text-xs text-muted-foreground">
        {[row.number, row.body].filter(Boolean).join(" · ")}
      </p>
      <Link
        to={`/review/geschaefte/${row.affairId}`}
        className="text-base leading-snug font-medium underline-offset-4 hover:underline"
      >
        {row.title}
      </Link>
    </td>
  )
}

function OpenTable({ rows }: { rows: QueueRow[] }) {
  const sort = useSort<OpenKey>("confidence", "asc")
  const sorted = sortRows(rows, sort.key, sort.dir)
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
          {sorted.map((row) => (
            <tr
              key={`${row.affairId}|${row.tagId}`}
              className="border-b border-border align-top"
            >
              <AffairCell row={row} />
              <td className="px-3 py-3">{row.labelName}</td>
              <td className="px-3 py-3 whitespace-nowrap">
                <Confidence value={row.confidence} />
              </td>
              <td className="px-3 py-3 text-xs">{row.reasons.join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
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
  const [topic, setTopic] = useState(ALL)
  const live = useReviewQueue()
  const queue = buildQueue(live.candidates, review.decisions)
  const topics = [...new Set(queue.map((row) => row.labelName))].sort()
  const rows =
    topic === ALL ? queue : queue.filter((row) => row.labelName === topic)
  const open = rows.filter((row) => !row.entry)
  const done = rows.filter((row) => row.entry)

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
          <ReviewSignIn />
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
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 id="queue-heading" className="font-heading text-lg font-medium">
            Offen ({open.length})
          </h2>
          {topics.length > 1 && (
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              Thema
              <select
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
                className="h-7 rounded-md border border-input bg-background px-2 text-sm text-foreground"
              >
                <option value={ALL}>Alle Themen</option>
                {topics.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {live.loading && (
          <p className="text-muted-foreground">Labels werden geladen …</p>
        )}
        {live.error && (
          <p className="text-sm text-destructive">
            Labels nicht geladen: {live.error}
          </p>
        )}
        {live.loading || live.error ? null : open.length > 0 ? (
          <OpenTable rows={open} />
        ) : (
          <p className="text-muted-foreground">
            {done.length > 0 ? "Alles geprüft." : "Nichts zu prüfen."}
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
      <section
        aria-labelledby="processing-heading"
        className="flex flex-col gap-3 pt-4"
      >
        <h2
          id="processing-heading"
          className="font-heading text-lg font-medium"
        >
          Verarbeitungsstand
        </h2>
        <SystemList />
        <JobTable />
      </section>
    </>
  )
}
