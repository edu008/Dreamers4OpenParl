import { Link } from "react-router"

import { PlainHeader } from "@/components/sort-header"
import { buttonVariants } from "@/components/ui/button"
import { useApi } from "@/hooks/use-api"

/** GET /v1/eval/calibration: Trefferquote der Modell-Labels je Konfidenzband. */
interface Calibration {
  threshold: number
  reviewed: number
  confirmed: number
  bands: {
    low: number
    high: number
    reviewed: number
    confirmed: number
    precision: number | null
    sample_reviewed: number
    sample_confirmed: number
    sample_precision: number | null
  }[]
}

const number = new Intl.NumberFormat("de-CH")
const decimal = new Intl.NumberFormat("de-CH", { minimumFractionDigits: 1 })
const NUM_HEAD = "px-3 py-2 text-right text-xs font-semibold"
const NUM_CELL = "tabular px-3 py-2 text-right whitespace-nowrap"

function percent(share: number | null): string {
  return share === null ? "–" : `${Math.round(share * 100)} %`
}

// Wie ehrlich ist die Konfidenz? Je Band der Anteil der Modell-Labels, die ein Mensch bestätigt
// hat. Für den Bericht zählt die Stichprobe, denn die übrige Prüfung wählt tiefe Konfidenz aus.
export function CalibrationPanel() {
  const calibration = useApi<Calibration>("/v1/eval/calibration")

  if (calibration.loading) {
    return <p className="text-muted-foreground">Wird geladen …</p>
  }
  if (calibration.error || !calibration.data) {
    return (
      <p className="text-sm text-destructive">
        Qualität nicht geladen: {calibration.error}
      </p>
    )
  }
  const { threshold, reviewed, confirmed, bands } = calibration.data

  return (
    <div className="flex flex-col gap-4">
      {reviewed === 0 ? (
        <p className="max-w-[68ch] text-sm text-muted-foreground">
          Noch keine Entscheide zu Modell-Labels, darum noch keine Trefferquote.
          Sie entsteht in der{" "}
          <Link
            to="/admin/review"
            className="underline underline-offset-2 hover:text-primary"
          >
            Prüfung
          </Link>
          .
        </p>
      ) : (
        <>
          <p className="max-w-[68ch] text-sm">
            <span className="tabular font-semibold">
              {number.format(confirmed)}
            </span>{" "}
            von{" "}
            <span className="tabular font-semibold">
              {number.format(reviewed)}
            </span>{" "}
            geprüften Modell-Labels bestätigt (
            <span className="tabular">{percent(confirmed / reviewed)}</span>).
            Verworfen und ersetzt zählen als falsch.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] table-fixed border-collapse text-sm">
              <caption className="sr-only">
                Trefferquote je Konfidenzband
              </caption>
              <thead className="border-b border-border bg-margin-tint">
                <tr>
                  <PlainHeader>Konfidenz</PlainHeader>
                  <th scope="col" className={NUM_HEAD}>
                    Bestätigt
                  </th>
                  <th scope="col" className={NUM_HEAD}>
                    Trefferquote
                  </th>
                  <th scope="col" className={NUM_HEAD}>
                    Stichprobe
                  </th>
                  <th scope="col" className={NUM_HEAD}>
                    Trefferquote Stichprobe
                  </th>
                </tr>
              </thead>
              <tbody>
                {bands.map((band) => (
                  <tr key={band.low} className="border-b border-border">
                    <td className="tabular px-3 py-2">
                      {decimal.format(band.low)} – {decimal.format(band.high)}
                      {band.high <= threshold && (
                        <span className="block text-xs text-muted-foreground">
                          unter der Schwelle
                        </span>
                      )}
                    </td>
                    <td className={NUM_CELL}>
                      {number.format(band.confirmed)} /{" "}
                      {number.format(band.reviewed)}
                    </td>
                    <td className={NUM_CELL}>{percent(band.precision)}</td>
                    <td className={NUM_CELL}>
                      {number.format(band.sample_confirmed)} /{" "}
                      {number.format(band.sample_reviewed)}
                    </td>
                    <td className={NUM_CELL}>
                      {percent(band.sample_precision)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="max-w-[68ch] text-xs text-muted-foreground">
            Schwelle für tiefe Konfidenz: {decimal.format(threshold)}. Die
            Stichprobe ist jedes 50. Geschäft; sie ist unabhängig davon, was die
            Prüfung auswählt, und darum die Zahl für den Bericht.
          </p>
        </>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <a
          href="/v1/eval/gold"
          download="gold-set.json"
          className={buttonVariants({ variant: "outline", size: "sm" })}
        >
          Gold-Set herunterladen
        </a>
        <span className="text-xs text-muted-foreground">
          Alle Entscheide von Menschen als JSON, mit Modell-, Prompt- und
          Registry-Version.
        </span>
      </div>
    </div>
  )
}
