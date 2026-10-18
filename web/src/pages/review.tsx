import { useState } from "react"
import { Link } from "react-router"

import { Confidence } from "@/components/confidence"
import { useReview } from "@/hooks/use-review"
import { buildQueue, openRows } from "@/lib/review-queue"

const HEAD = "px-3 py-2 text-left text-xs font-medium text-muted-foreground"
const ALL = "alle"

// Warteschlange: Labels mit Prüfbedarf, die unsichersten zuerst. Entschiedene rücken ans Ende.
export function ReviewPage() {
  const review = useReview()
  const [topic, setTopic] = useState(ALL)
  const queue = buildQueue(review.decisions)
  const topics = [...new Set(queue.map((row) => row.label.name))].sort()
  const rows = topic === ALL ? queue : queue.filter((row) => row.label.name === topic)
  const open = openRows(rows).length

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
        className="flex flex-col gap-3 border-t border-foreground pt-4"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 id="queue-heading" className="font-heading text-lg font-medium">
            Offen: {open}
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
        {rows.length === 0 ? (
          <p className="text-muted-foreground">Nichts zu prüfen.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[34rem] border-collapse text-sm">
              <caption className="sr-only">Labels mit Prüfbedarf</caption>
              <thead className="border-y border-foreground">
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
                    Stand
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ affair, label, reasons, entry }) => (
                  <tr
                    key={`${affair.id}|${label.tagId}`}
                    className="border-b border-border align-top"
                  >
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
                    <td className="px-3 py-3">{label.name}</td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      <Confidence value={label.confidence} />
                    </td>
                    <td className="px-3 py-3 text-xs">
                      {entry ? (
                        <span className="font-semibold">
                          {entry.decision === "confirmed"
                            ? "Bestätigt"
                            : "Verworfen"}{" "}
                          von {entry.by}
                        </span>
                      ) : (
                        <span className="font-semibold text-level-medium">
                          {reasons.join(", ")}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
