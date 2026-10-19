import { useMemo, useState } from "react"

import { Distribution } from "@/components/distribution"
import { useApi } from "@/hooks/use-api"
import { LEVEL_LABEL } from "@/lib/export"

const number = new Intl.NumberFormat("de-CH")

interface Body {
  body_key: string
  name: string | null
  level: string | null
  /** Geschäfte mit mindestens einem aktiven Label. */
  n_affairs: number
}

interface BodyDetail {
  body_key: string
  name: Record<string, string>
  type_name: Record<string, string>
  legislative_name: Record<string, string>
  languages: string | null
  population?: number | null
  n_affairs: number
  n_labelled: number
}

const LEVELS = ["country", "canton", "city", "municipality"]

function levelName(level: string | null): string {
  return level ? (LEVEL_LABEL[level] ?? level) : "–"
}

/** Einzelheiten eines Parlaments; geladen erst, wenn die Zeile aufgeklappt wird. */
function BodyFacts({ bodyKey }: { bodyKey: string }) {
  const detail = useApi<BodyDetail>(`/v1/bodies/${encodeURIComponent(bodyKey)}`)
  if (detail.loading) {
    return <p className="text-xs text-muted-foreground">Wird geladen …</p>
  }
  if (detail.error || !detail.data) {
    return (
      <p className="text-xs text-destructive">
        Nicht geladen: {detail.error}
      </p>
    )
  }
  const d = detail.data
  const share = d.n_affairs === 0 ? 0 : (d.n_labelled / d.n_affairs) * 100
  const rows: [string, string][] = [
    ["Parlament", d.legislative_name.de ?? "–"],
    ["Sprache", d.languages ?? "–"],
    ["Bevölkerung", d.population ? number.format(d.population) : "–"],
    ["Geschäfte in der Datenbank", number.format(d.n_affairs)],
    [
      "Davon klassifiziert",
      `${number.format(d.n_labelled)} (${share < 1 && d.n_labelled > 0 ? share.toFixed(2) : Math.round(share)} %)`,
    ],
  ]
  return (
    <dl className="grid max-w-md grid-cols-[11rem_minmax(0,1fr)] gap-x-4 gap-y-1 text-xs">
      {rows.map(([name, value]) => (
        <div key={name} className="contents">
          <dt className="text-muted-foreground">{name}</dt>
          <dd className="tabular">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

// Parlamente mit klassifizierten Geschäften. Zeigt, wo die Klassifikation schon hinreicht; die
// Abdeckung je Ebene und Parlament gehört zur Bias-Prüfung nach Region und Ebene (Challenge 5).
export function BodiesPage() {
  const bodies = useApi<Body[]>("/v1/bodies")
  const [level, setLevel] = useState<string | null>(null)

  const byLevel = useMemo(() => {
    const counts = new Map<string, number>()
    for (const body of bodies.data ?? []) {
      const key = body.level ?? "other"
      counts.set(key, (counts.get(key) ?? 0) + body.n_affairs)
    }
    return [...counts.entries()]
      .map(([key, count]) => ({
        key,
        label: levelName(key === "other" ? null : key),
        count,
      }))
      .sort((a, b) => LEVELS.indexOf(a.key) - LEVELS.indexOf(b.key))
  }, [bodies.data])

  const rows = (bodies.data ?? [])
    .filter((body) => level === null || body.level === level)
    .sort((a, b) => b.n_affairs - a.n_affairs)
  const total = (bodies.data ?? []).reduce((sum, body) => sum + body.n_affairs, 0)
  const max = Math.max(1, ...rows.map((body) => body.n_affairs))

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
          Parlamente
        </h1>
        <p className="max-w-[68ch] text-muted-foreground">
          Parlamente mit klassifizierten Geschäften. Das zeigt, wo die
          Klassifikation schon hinreicht und wo noch nicht, die Voraussetzung für
          eine Prüfung auf Verzerrung nach Ebene und Region.
        </p>
      </div>

      {bodies.loading && <p className="text-muted-foreground">Wird geladen …</p>}
      {bodies.error && (
        <p className="text-sm text-destructive">
          Parlamente nicht geladen: {bodies.error}
        </p>
      )}

      {bodies.data && (
        <>
          <p className="tabular text-sm">
            <span className="font-semibold">{bodies.data.length}</span>{" "}
            Parlamente mit{" "}
            <span className="font-semibold">{number.format(total)}</span>{" "}
            klassifizierten Geschäften.
          </p>
          <div className="max-w-md">
            <Distribution
              title="Geschäfte nach Ebene"
              rows={byLevel}
              activeKey={level}
              onPick={setLevel}
            />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[34rem] border-collapse text-sm">
              <caption className="sr-only">Parlamente mit klassifizierten Geschäften</caption>
              <thead className="border-b border-border bg-margin-tint">
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-xs font-semibold">
                    Parlament
                  </th>
                  <th scope="col" className="px-3 py-2 text-left text-xs font-semibold">
                    Ebene
                  </th>
                  <th scope="col" className="px-3 py-2 text-left text-xs font-semibold">
                    Klassifizierte Geschäfte
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((body) => (
                  <tr key={body.body_key} className="border-b border-border align-top">
                    <td className="px-3 py-2">
                      <details>
                        <summary className="cursor-pointer py-1 underline-offset-2 hover:underline">
                          {body.name ?? body.body_key}
                        </summary>
                        <div className="py-2">
                          <BodyFacts bodyKey={body.body_key} />
                        </div>
                      </details>
                    </td>
                    <td className="px-3 py-2">{levelName(body.level)}</td>
                    <td className="px-3 py-2">
                      <span className="flex items-center gap-2">
                        <span aria-hidden="true" className="h-1.5 w-32 bg-border">
                          <span
                            className="block h-full bg-primary"
                            style={{ width: `${(body.n_affairs / max) * 100}%` }}
                          />
                        </span>
                        <span className="tabular w-14 text-right font-semibold">
                          {number.format(body.n_affairs)}
                        </span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}
