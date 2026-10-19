import { PlainHeader } from "@/components/sort-header"
import { useApi } from "@/hooks/use-api"
import {
  formatDuration,
  formatHours,
  RUN_KIND,
  type RunsSummary,
  type Stats,
} from "@/lib/runs"

const number = new Intl.NumberFormat("de-CH")
const NUM_HEAD = "px-3 py-2 text-right text-xs font-semibold"

function formatStart(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString("de-CH", { dateStyle: "short", timeStyle: "short" })
}

// Durchsatz und Hochrechnung: Wie schnell klassifiziert das System, und wie lange dauert der
// ganze Bestand bei diesem Tempo? Das ist die Antwort auf «feasible runtime for 300,000+ affairs».
export function RunsPanel() {
  const summary = useApi<RunsSummary>("/v1/jobs/summary")
  const stats = useApi<Stats>("/v1/stats")

  if (summary.loading) {
    return <p className="text-muted-foreground">Wird geladen …</p>
  }
  if (summary.error || !summary.data) {
    return (
      <p className="text-sm text-destructive">
        Läufe nicht geladen: {summary.error}
      </p>
    )
  }
  const { runs, errors } = summary.data
  // Das neueste Tempo eines Laufs, der wirklich Geschäfte geschafft hat.
  const tempo = runs.find((run) => (run.per_minute ?? 0) > 0)
  const remaining = stats.data
    ? Math.max(0, stats.data.affairs - stats.data.classified)
    : null
  const hours =
    tempo?.per_minute && remaining !== null
      ? remaining / tempo.per_minute / 60
      : null
  const share = stats.data
    ? (stats.data.classified / Math.max(1, stats.data.affairs)) * 100
    : null

  return (
    <div className="flex flex-col gap-4">
      {stats.data && (
        <div className="flex flex-col gap-2">
          <p className="text-sm">
            <span className="tabular font-semibold">
              {number.format(stats.data.classified)}
            </span>{" "}
            von{" "}
            <span className="tabular font-semibold">
              {number.format(stats.data.affairs)}
            </span>{" "}
            Geschäften klassifiziert
            {share !== null && (
              <span className="tabular text-muted-foreground">
                {" "}
                ({share < 1 ? share.toFixed(1) : Math.round(share)} %)
              </span>
            )}
            , dazu {number.format(stats.data.labels)} Labels und{" "}
            {number.format(stats.data.reviewed)} Entscheide von Menschen.
          </p>
          <div
            role="progressbar"
            aria-label="Anteil klassifizierter Geschäfte"
            aria-valuemin={0}
            aria-valuemax={stats.data.affairs}
            aria-valuenow={stats.data.classified}
            className="h-1 w-full max-w-xl bg-border"
          >
            <div
              className="h-full bg-primary"
              style={{ width: `${Math.max(0.5, share ?? 0)}%` }}
            />
          </div>
        </div>
      )}

      {tempo?.per_minute && hours !== null && remaining !== null ? (
        <p className="max-w-[68ch] text-sm">
          Aktuelles Tempo:{" "}
          <span className="tabular font-semibold">
            {number.format(Math.round(tempo.per_minute))}
          </span>{" "}
          Geschäfte je Minute ({RUN_KIND[tempo.kind]}, {tempo.task}). Bei diesem
          Tempo sind die restlichen{" "}
          <span className="tabular font-semibold">
            {number.format(remaining)}
          </span>{" "}
          Geschäfte in {formatHours(hours)} klassifiziert.
          <span className="block pt-1 text-xs text-muted-foreground">
            Das Tempo hängt vom Modell-Endpunkt und der Zahl paralleler Anfragen
            ab; die Hochrechnung ändert sich mit dem nächsten Lauf.
          </span>
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">
          Noch kein Lauf mit gemessenem Tempo, deshalb gibt es keine
          Hochrechnung.
        </p>
      )}

      {runs.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[44rem] table-fixed border-collapse text-sm">
            <caption className="sr-only">Die letzten Läufe</caption>
            <colgroup>
              <col style={{ width: "22%" }} />
              <col style={{ width: "16%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "11%" }} />
              <col style={{ width: "11%" }} />
            </colgroup>
            <thead className="border-b border-border bg-margin-tint">
              <tr>
                <PlainHeader>Lauf</PlainHeader>
                <PlainHeader>Start</PlainHeader>
                <th scope="col" className={NUM_HEAD}>
                  Dauer
                </th>
                <th scope="col" className={NUM_HEAD}>
                  Fertig
                </th>
                <th scope="col" className={NUM_HEAD}>
                  je Minute
                </th>
                <th scope="col" className={NUM_HEAD}>
                  Fehler
                </th>
                <th scope="col" className={NUM_HEAD}>
                  An 70B
                </th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="border-b border-border align-top">
                  <td className="px-3 py-2 break-words">
                    {RUN_KIND[run.kind]}
                    <span className="block text-xs text-muted-foreground">
                      {run.task}
                      {run.finished_at === null ? " · läuft" : ""}
                    </span>
                  </td>
                  <td className="tabular px-3 py-2 text-xs">
                    {formatStart(run.started_at)}
                  </td>
                  <td className="tabular px-3 py-2 text-right whitespace-nowrap">
                    {formatDuration(run.duration_s)}
                  </td>
                  <td className="tabular px-3 py-2 text-right whitespace-nowrap">
                    {number.format(run.n_done)} / {number.format(run.n_total)}
                  </td>
                  <td className="tabular px-3 py-2 text-right whitespace-nowrap">
                    {run.per_minute === null
                      ? "–"
                      : number.format(Math.round(run.per_minute))}
                  </td>
                  <td className="tabular px-3 py-2 text-right">
                    {number.format(run.n_failed)}
                  </td>
                  <td className="tabular px-3 py-2 text-right">
                    {number.format(run.n_escalated)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {errors.length > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="text-xs font-semibold">Häufigste Fehlergründe</h3>
          <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
            {errors.map((error) => (
              <li key={`${error.task}|${error.reason}`}>
                <span className="tabular font-semibold text-foreground">
                  {number.format(error.count)}×
                </span>{" "}
                {error.reason}{" "}
                <span className="text-muted-foreground">({error.task})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
