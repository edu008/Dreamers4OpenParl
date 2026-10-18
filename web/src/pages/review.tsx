import { useState } from "react"
import { Link } from "react-router"

import { Confidence } from "@/components/confidence"
import { Button } from "@/components/ui/button"
import { useReview } from "@/hooks/use-review"
import { reviewKey } from "@/lib/review"
import { buildQueue, type QueueRow } from "@/lib/review-queue"

const HEAD = "px-3 py-2 text-left text-xs font-semibold text-foreground"
const ALL = "alle"

function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("de-CH")
}

function AffairCell({ row }: { row: QueueRow }) {
  const { affair } = row
  return (
    <td className="max-w-[22rem] px-3 py-3">
      <p className="tabular text-xs text-muted-foreground">
        {affair.number} · {affair.body}
      </p>
      <Link
        to={`/geschaefte/${affair.id}`}
        lang={affair.language}
        className="font-reading text-base leading-snug font-semibold underline-offset-4 hover:underline"
      >
        {affair.title}
      </Link>
    </td>
  )
}

function OpenTable({ rows }: { rows: QueueRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] border-collapse text-sm">
        <caption className="sr-only">Labels mit Prüfbedarf</caption>
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={HEAD}>
              Geschäft
            </th>
            <th scope="col" className={HEAD}>
              Label
            </th>
            <th scope="col" className={HEAD}>
              Konfidenz
            </th>
            <th scope="col" className={HEAD}>
              Grund
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={`${row.affair.id}|${row.label.tagId}`}
              className="border-b border-border align-top"
            >
              <AffairCell row={row} />
              <td className="px-3 py-3">{row.label.name}</td>
              <td className="px-3 py-3 whitespace-nowrap">
                <Confidence value={row.label.confidence} />
              </td>
              <td className="px-3 py-3 text-xs font-semibold text-level-medium">
                {row.reasons.join(", ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DoneTable({ rows }: { rows: QueueRow[] }) {
  const review = useReview()
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] border-collapse text-sm">
        <caption className="sr-only">Entschiedene Labels</caption>
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={HEAD}>
              Geschäft
            </th>
            <th scope="col" className={HEAD}>
              Label
            </th>
            <th scope="col" className={HEAD}>
              Entscheid
            </th>
            <th scope="col" className={HEAD}>
              <span className="sr-only">Aktion</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const entry = row.entry
            if (!entry) return null
            const key = reviewKey(row.affair.id, row.label.tagId)
            return (
              <tr key={key} className="border-b border-border align-top">
                <AffairCell row={row} />
                <td className="px-3 py-3">{row.label.name}</td>
                <td className="px-3 py-3 text-xs">
                  <span className="font-semibold">
                    {entry.decision === "confirmed" ? "Bestätigt" : "Verworfen"}
                  </span>{" "}
                  von {entry.by}
                  <span className="tabular block text-muted-foreground">
                    {formatDate(entry.at)}
                  </span>
                </td>
                <td className="px-3 py-3">
                  {review.active && (
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => review.undo(key)}
                    >
                      Rückgängig
                    </Button>
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

// Arbeitsliste: Labels mit Prüfbedarf, die unsichersten zuerst. Entschiedene stehen getrennt,
// eingeklappt, damit die Liste oben nur zeigt, was noch zu tun ist.
export function ReviewPage() {
  const review = useReview()
  const [topic, setTopic] = useState(ALL)
  const queue = buildQueue(review.decisions)
  const topics = [...new Set(queue.map((row) => row.label.name))].sort()
  const rows =
    topic === ALL ? queue : queue.filter((row) => row.label.name === topic)
  const open = rows.filter((row) => !row.entry)
  const done = rows.filter((row) => row.entry)

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="font-reading text-2xl leading-tight font-semibold text-balance">
          Review
        </h1>
        <p className="max-w-[68ch] text-muted-foreground">
          Labels sind Vorschläge. Hier stehen die unsichersten zuerst: niedrige
          Konfidenz oder ein Beleg, der nicht im Text steht. Öffne das Geschäft,
          lies den Beleg und entscheide.
        </p>
        {!review.active && (
          <p className="text-xs text-muted-foreground">
            Zum Entscheiden den Review-Modus oben rechts einschalten.
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          Beispieldaten, nicht aus OpenParlData. Entscheide gelten nur in diesem
          Browser.
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
        {open.length > 0 ? (
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
    </>
  )
}
