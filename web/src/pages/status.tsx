import { PlainHeader } from "@/components/sort-header"
import { useApi } from "@/hooks/use-api"
import type { Health, PageTree } from "@/lib/api"

interface JobRow {
  task: string
  open: number
  pending: number
  done: number
  failed: number
}

// Beispielzahlen, bis GET /v1/jobs/summary die Jobs aus classification_jobs liefert (M3).
const SAMPLE_JOBS: JobRow[] = [
  {
    task: "classify:aps",
    open: 41230,
    pending: 16,
    done: 28774,
    failed: 52,
  },
  {
    task: "classify:adhoc:digitalisierung-breit",
    open: 5120,
    pending: 8,
    done: 2290,
    failed: 3,
  },
]

const number = new Intl.NumberFormat("de-CH")

function percentDone(row: JobRow): string {
  const total = row.open + row.pending + row.done + row.failed
  return total === 0 ? "–" : `${Math.round((row.done / total) * 100)} %`
}

function Cell({ value }: { value: number }) {
  return (
    <td className="tabular px-3 py-3 text-right whitespace-nowrap">
      {number.format(value)}
    </td>
  )
}

function SystemList() {
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

export function StatusPage() {
  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
          Status
        </h1>
        <p className="max-w-[68ch] text-muted-foreground">
          Hier sieht man, ob das System läuft und wie weit die Klassifikation
          ist.
        </p>
      </div>

      <section
        aria-labelledby="system-heading"
        className="flex flex-col gap-3 pt-2"
      >
        <h2 id="system-heading" className="font-heading text-lg font-medium">
          System
        </h2>
        <SystemList />
      </section>

      <section
        aria-labelledby="jobs-heading"
        className="flex flex-col gap-3 pt-2"
      >
        <h2 id="jobs-heading" className="font-heading text-lg font-medium">
          Klassifikation
        </h2>
        <p className="text-xs text-muted-foreground">
          Beispielzahlen, nicht aus der Datenbank. Echte Zahlen folgen mit der
          Klassifikation.
        </p>
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
                <th
                  scope="col"
                  className="px-3 py-2 text-right text-xs font-semibold"
                >
                  Offen
                </th>
                <th
                  scope="col"
                  className="px-3 py-2 text-right text-xs font-semibold"
                >
                  In Arbeit
                </th>
                <th
                  scope="col"
                  className="px-3 py-2 text-right text-xs font-semibold"
                >
                  Fertig
                </th>
                <th
                  scope="col"
                  className="px-3 py-2 text-right text-xs font-semibold"
                >
                  Fehlgeschlagen
                </th>
                <th
                  scope="col"
                  className="px-3 py-2 text-right text-xs font-semibold"
                >
                  Anteil fertig
                </th>
              </tr>
            </thead>
            <tbody>
              {SAMPLE_JOBS.map((row) => (
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
      </section>
    </>
  )
}
