import { Link } from "react-router"

import { useApi } from "@/hooks/use-api"
import type { WikiPage } from "@/lib/api"

/** Ausschnitt aus GET /v1/pages/{id} (PageDetail): der Stand aus dem Seitenlauf (F23–F25). */
interface PageSummaryOut {
  summary: {
    page_status: "open" | "pending" | "done" | "failed"
    n_affairs: number
    summary_short: string | null
    summary_long: string | null
    statements: { text: string; affair_ids: number[]; page_ids: string[] }[]
    built_at: string | null
    window_start: string | null
    window_end: string | null
    model_version: string | null
  } | null
}

function formatDate(iso: string | null): string {
  if (!iso) return ""
  const [year, month, day] = iso.slice(0, 10).split("-")
  return `${day}.${month}.${year}`
}

// Zusammenfassung einer Themen-, Kapitel- oder Bereichsseite aus dem Seitenlauf
// (`parltopics pages`). Jede Aussage nennt ihre Geschäfte und Unterseiten. Ohne Lauf oder ohne
// Text bleibt der Abschnitt weg; der Stand steht dann nur im Seitenbaum.
export function PageSummary({
  pageId,
  pages,
}: {
  pageId: string
  /** Seitenbaum, damit verlinkte Seiten mit Titel statt ID erscheinen. */
  pages: WikiPage[]
}) {
  const detail = useApi<PageSummaryOut>(
    `/v1/pages/${encodeURIComponent(pageId)}`
  )
  const summary = detail.data?.summary
  const text = summary?.summary_long ?? summary?.summary_short
  if (!summary || !text) return null
  const window = [
    formatDate(summary.window_start),
    formatDate(summary.window_end),
  ]
  return (
    <section
      aria-labelledby="summary-heading"
      className="flex flex-col gap-4 border-l-4 border-foreground bg-muted p-5"
    >
      <h2 id="summary-heading" className="text-base font-bold">
        Zusammenfassung
      </h2>
      <p className="max-w-[68ch] leading-relaxed">{text}</p>
      {summary.statements.length > 0 && (
        <ul className="flex max-w-[68ch] flex-col gap-2 text-sm">
          {summary.statements.map((statement) => (
            <li key={statement.text} className="flex flex-col gap-1">
              <span>{statement.text}</span>
              <span className="flex flex-wrap gap-x-3 text-muted-foreground">
                {statement.affair_ids.map((id) => (
                  <Link
                    key={id}
                    to={`/admin/review/geschaefte/${id}`}
                    className="tabular underline underline-offset-2 hover:text-primary"
                  >
                    Geschäft {id}
                  </Link>
                ))}
                {statement.page_ids.map((id) => (
                  <Link
                    key={id}
                    to={`/admin/themen/${id}`}
                    className="underline underline-offset-2 hover:text-primary"
                  >
                    {pages.find((page) => page.page_id === id)?.title ?? id}
                  </Link>
                ))}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-sm text-muted-foreground">
        {[
          summary.built_at && `Stand ${formatDate(summary.built_at)}`,
          window[0] && window[1] && `Zeitfenster ${window[0]} bis ${window[1]}`,
          summary.model_version,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
    </section>
  )
}
