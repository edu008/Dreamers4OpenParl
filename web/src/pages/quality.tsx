import { Link } from "react-router"

import { useApi } from "@/hooks/use-api"
import type { Stats } from "@/lib/runs"

const number = new Intl.NumberFormat("de-CH")

interface Band {
  low: number
  high: number
  reviewed: number
  confirmed: number
  precision: number | null
  sample_reviewed: number
  sample_confirmed: number
  sample_precision: number | null
}

interface Calibration {
  threshold: number
  reviewed: number
  confirmed: number
  bands: Band[]
}

interface GoldLabel {
  affair_id: number
  decision: string
  sample: boolean
}

function percent(value: number | null): string {
  return value === null ? "–" : `${Math.round(value * 100)} %`
}

/** Waagrechter Balken für einen Anteil (0 bis 1); fehlt der Wert, bleibt der Platz leer. */
function Rate({ value }: { value: number | null }) {
  return (
    <span className="flex items-center gap-2">
      <span aria-hidden="true" className="h-1.5 w-20 bg-border">
        {value !== null && (
          <span
            className="block h-full bg-foreground"
            style={{ width: `${value * 100}%` }}
          />
        )}
      </span>
      <span className="tabular w-10 text-right font-semibold">
        {percent(value)}
      </span>
    </span>
  )
}

// Qualität der Klassifikation: Wie ehrlich ist die Konfidenz? Je Konfidenzband der Anteil der
// Modell-Labels, die ein Mensch bestätigt hat. Die Zahlen entstehen aus den Entscheiden im Review.
export function QualityPage() {
  const calibration = useApi<Calibration>("/v1/eval/calibration")
  const gold = useApi<GoldLabel[]>("/v1/eval/gold")
  const stats = useApi<Stats>("/v1/stats")

  const data = calibration.data
  const reviewed = data?.reviewed ?? 0
  const sampleReviewed = data
    ? data.bands.reduce((sum, band) => sum + band.sample_reviewed, 0)
    : 0
  const sampleConfirmed = data
    ? data.bands.reduce((sum, band) => sum + band.sample_confirmed, 0)
    : 0

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
          Qualität der Klassifikation
        </h1>
        <p className="max-w-[68ch] text-muted-foreground">
          Ein Label ist ein Vorschlag des Modells mit einer Konfidenz. Hier
          steht, wie oft Menschen die Vorschläge im Review bestätigt haben, je
          Konfidenzband. Stimmt die Konfidenz, liegt die Trefferquote in hohen
          Bändern hoch und in tiefen niedrig.
        </p>
      </div>

      {calibration.loading && (
        <p className="text-muted-foreground">Wird geladen …</p>
      )}
      {calibration.error && (
        <p className="text-sm text-destructive">
          Auswertung nicht geladen: {calibration.error}
        </p>
      )}

      {data && reviewed === 0 && (
        <section
          aria-labelledby="empty-heading"
          className="flex max-w-[68ch] flex-col gap-2"
        >
          <h2 id="empty-heading" className="font-heading text-lg font-medium">
            Noch keine Entscheide von Menschen
          </h2>
          <p className="text-sm text-muted-foreground">
            Die Trefferquote entsteht aus bestätigten und verworfenen Labels.
            Bisher hat niemand im Review entschieden
            {stats.data
              ? `, bei ${number.format(stats.data.labels)} Labels`
              : ""}
            . Sobald das geschieht, erscheinen hier die Zahlen je Konfidenzband.
          </p>
          <p>
            <Link
              to="/admin/review"
              className="py-2 text-sm underline underline-offset-2"
            >
              Zum Review
            </Link>
          </p>
        </section>
      )}

      {data && reviewed > 0 && (
        <section
          aria-labelledby="bands-heading"
          className="flex flex-col gap-3"
        >
          <h2 id="bands-heading" className="font-heading text-lg font-medium">
            Trefferquote je Konfidenzband
          </h2>
          <p className="tabular text-sm">
            <span className="font-semibold">{number.format(reviewed)}</span>{" "}
            Labels mit Entscheid, davon{" "}
            <span className="font-semibold">
              {number.format(data.confirmed)}
            </span>{" "}
            bestätigt ({percent(data.confirmed / Math.max(1, reviewed))}).
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem] border-collapse text-sm">
              <caption className="sr-only">
                Trefferquote je Konfidenzband
              </caption>
              <thead className="border-b border-border bg-margin-tint">
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-xs font-semibold">
                    Konfidenz
                  </th>
                  <th scope="col" className="px-3 py-2 text-right text-xs font-semibold">
                    Mit Entscheid
                  </th>
                  <th scope="col" className="px-3 py-2 text-left text-xs font-semibold">
                    Bestätigt
                  </th>
                  <th scope="col" className="px-3 py-2 text-right text-xs font-semibold">
                    In der Stichprobe
                  </th>
                  <th scope="col" className="px-3 py-2 text-left text-xs font-semibold">
                    Bestätigt (Stichprobe)
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.bands.map((band) => (
                  <tr
                    key={band.low}
                    className="border-b border-border align-middle"
                  >
                    <td className="tabular px-3 py-2">
                      {band.low.toFixed(1)} bis{" "}
                      {band.high >= 1 ? "1.0" : `unter ${band.high.toFixed(1)}`}
                      {band.low < data.threshold && band.high <= data.threshold && (
                        <span className="block text-xs text-muted-foreground">
                          unter der Schwelle {data.threshold}
                        </span>
                      )}
                    </td>
                    <td className="tabular px-3 py-2 text-right">
                      {number.format(band.reviewed)}
                    </td>
                    <td className="px-3 py-2">
                      <Rate value={band.precision} />
                    </td>
                    <td className="tabular px-3 py-2 text-right">
                      {number.format(band.sample_reviewed)}
                    </td>
                    <td className="px-3 py-2">
                      <Rate value={band.sample_precision} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="max-w-[68ch] text-xs text-muted-foreground">
            Die Warteschlange im Review wählt nach tiefer Konfidenz aus und
            verzerrt so die Quote. Für den Bericht zählt deshalb die
            Stichprobe (jedes 50. Geschäft, unabhängig von der Konfidenz):{" "}
            {number.format(sampleReviewed)} Labels, davon{" "}
            {number.format(sampleConfirmed)} bestätigt.
          </p>
        </section>
      )}

      <section
        aria-labelledby="gold-heading"
        className="flex max-w-[68ch] flex-col gap-2"
      >
        <h2 id="gold-heading" className="font-heading text-lg font-medium">
          Gold-Set
        </h2>
        <p className="text-sm text-muted-foreground">
          Alle Entscheide von Menschen als Vergleichsmenge für spätere
          Auswertungen, mit Modell-, Prompt- und Registry-Version und dem Text,
          auf den sich der Entscheid bezieht.
          {gold.data
            ? ` Aktuell ${number.format(gold.data.length)} Einträge${
                gold.data.filter((label) => label.sample).length > 0
                  ? `, davon ${number.format(gold.data.filter((label) => label.sample).length)} aus der Stichprobe`
                  : ""
              }.`
            : ""}
        </p>
        <p>
          <a
            href="/v1/eval/gold"
            download="parltopics-gold.json"
            className="py-2 text-sm underline underline-offset-2"
          >
            Gold-Set als JSON herunterladen
          </a>
        </p>
      </section>

      <section
        aria-labelledby="limits-heading"
        className="flex max-w-[68ch] flex-col gap-2"
      >
        <h2 id="limits-heading" className="font-heading text-lg font-medium">
          Grenzen dieser Auswertung
        </h2>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-muted-foreground">
          <li>
            Die Zahlen stammen aus den Entscheiden einzelner Personen und sind
            nur so aussagekräftig wie deren Zahl.
          </li>
          <li>
            Eine Aufteilung nach Sprache, Ebene und Region (Bias-Prüfung) zeigt
            diese Seite noch nicht; die Entscheide tragen die Angaben dafür,
            das Backend liefert die Aufteilung aber noch nicht.
          </li>
          <li>
            «Bestätigt» heisst, das Thema gehört zum Geschäft. Verworfene und
            ersetzte Labels zählen als falsch.
          </li>
        </ul>
      </section>
    </>
  )
}
