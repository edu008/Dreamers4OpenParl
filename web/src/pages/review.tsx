import { Link } from "react-router"

import { Confidence } from "@/components/confidence"
import { useReview } from "@/hooks/use-review"
import { reviewReasons } from "@/lib/label-state"
import { reviewKey } from "@/lib/review"
import { SAMPLE_AFFAIRS } from "@/lib/sample-affairs"

const HEAD = "px-3 py-2 text-left text-xs font-medium text-muted-foreground"

// Warteschlange: Labels mit Prüfbedarf, die unsichersten zuerst. Entschiedene rücken ans Ende.
export function ReviewPage() {
  const review = useReview()
  const rows = SAMPLE_AFFAIRS.flatMap((affair) =>
    affair.labels.map((label) => ({
      affair,
      label,
      reasons: reviewReasons(affair, label),
      entry: review.decisions[reviewKey(affair.id, label.tagId)],
    }))
  )
    .filter((row) => row.reasons.length > 0 || row.entry)
    .sort(
      (a, b) =>
        Number(Boolean(a.entry)) - Number(Boolean(b.entry)) ||
        a.label.confidence - b.label.confidence
    )
  const open = rows.filter((row) => !row.entry).length

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
        className="flex flex-col gap-2 border-t border-foreground pt-4"
      >
        <h2 id="queue-heading" className="font-heading text-lg font-medium">
          Offen: {open}
        </h2>
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
