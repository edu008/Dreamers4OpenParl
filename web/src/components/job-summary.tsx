import { Link } from "react-router"

import { PlainHeader } from "@/components/sort-header"
import { useReview } from "@/hooks/use-review"
import { useApi } from "@/hooks/use-api"
import type { Health, JobCounts, JobsSummary, PageTree } from "@/lib/api"

const number = new Intl.NumberFormat("de-CH")

function percentDone(row: JobCounts): string {
  return row.total === 0 ? "–" : `${Math.round((row.done / row.total) * 100)} %`
}

function Cell({ value }: { value: number }) {
  return (
    <td className="tabular px-3 py-3 text-right whitespace-nowrap">
      {number.format(value)}
    </td>
  )
}

const NUM_HEAD = "px-3 py-2 text-right text-xs font-semibold"

/** System: API und Registry mit echten Werten aus /healthz und /v1/pages. */
export function SystemList() {
  const health = useApi<Health>("/healthz")
  const tree = useApi<PageTree>("/v1/pages")
  const rows: [string, string][] = [
    [
      "API",
      health.data
        ? `erreichbar, Version ${health.data.version}`
        : health.error
          ? "nicht erreichbar"
          : "wird geprüft",
    ],
    [
      "Registry",
      tree.data?.registry_version ?? (tree.error ? "nicht geladen" : "…"),
    ],
    ["Seiten im Themenbaum", tree.data ? String(tree.data.pages.length) : "…"],
  ]
  return (
    <dl className="grid max-w-xl grid-cols-[12rem_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
      {rows.map(([name, value]) => (
        <div key={name} className="contents">
          <dt className="text-muted-foreground">{name}</dt>
          <dd className="tabular">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

/** Jobs je Aufgabe und Status aus GET /v1/jobs/summary. */
export function JobTable() {
  const jobs = useApi<JobsSummary>("/v1/jobs/summary")
  if (jobs.loading) {
    return <p className="text-muted-foreground">Wird geladen …</p>
  }
  if (jobs.error || !jobs.data) {
    return (
      <p className="text-sm text-destructive">
        Jobs nicht geladen: {jobs.error}
      </p>
    )
  }
  if (jobs.data.tasks.length === 0) {
    return <p className="text-muted-foreground">Noch keine Jobs angelegt.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[38rem] table-fixed border-collapse text-sm">
        <caption className="sr-only">Jobs je Aufgabe und Status</caption>
        <colgroup>
          <col style={{ width: "34%" }} />
          <col style={{ width: "13%" }} />
          <col style={{ width: "13%" }} />
          <col style={{ width: "13%" }} />
          <col style={{ width: "14%" }} />
          <col style={{ width: "13%" }} />
        </colgroup>
        <thead className="border-b border-border bg-margin-tint">
          <tr>
            <PlainHeader>Aufgabe</PlainHeader>
            <th scope="col" className={NUM_HEAD}>
              Offen
            </th>
            <th scope="col" className={NUM_HEAD}>
              In Arbeit
            </th>
            <th scope="col" className={NUM_HEAD}>
              Fertig
            </th>
            <th scope="col" className={NUM_HEAD}>
              Fehlgeschlagen
            </th>
            <th scope="col" className={NUM_HEAD}>
              Anteil fertig
            </th>
          </tr>
        </thead>
        <tbody>
          {jobs.data.tasks.map((row) => (
            <tr key={row.task} className="border-b border-border align-top">
              <td className="px-3 py-3 break-words">{row.task}</td>
              <Cell value={row.open} />
              <Cell value={row.pending} />
              <Cell value={row.done} />
              <Cell value={row.failed} />
              <td className="tabular px-3 py-3 text-right font-semibold whitespace-nowrap">
                {percentDone(row)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Kurzer Stand der Klassifikation für die Seite "Review", mit Link zur Seite "Verarbeitungsstand". */
export function ProcessingBadge() {
  const jobs = useApi<JobsSummary>("/v1/jobs/summary")
  const { isAdmin } = useReview()
  if (!jobs.data || jobs.data.tasks.length === 0) return null
  const done = jobs.data.tasks.reduce((sum, task) => sum + task.done, 0)
  const total = jobs.data.tasks.reduce((sum, task) => sum + task.total, 0)
  return (
    <p className="text-xs text-muted-foreground">
      Klassifikation:{" "}
      <span className="tabular font-medium text-foreground">
        {number.format(done)} von {number.format(total)}
      </span>{" "}
      fertig
      {isAdmin && (
        <>
          {" "}
          ·{" "}
          <Link to="/admin" className="underline underline-offset-2">
            Details
          </Link>
        </>
      )}
    </p>
  )
}
