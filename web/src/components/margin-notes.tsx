import { Confidence } from "@/components/confidence"
import { Button } from "@/components/ui/button"
import { useReview } from "@/hooks/use-review"
import { reviewKey } from "@/lib/review"
import type { AffairLabel } from "@/lib/sample-affairs"

export interface MarginLabel extends AffairLabel {
  evidenceFound: boolean
  needsReview: boolean
}

const STAGE_NAME: Record<AffairLabel["stage"], string> = {
  "8b": "Apertus 8B",
  "70b": "Apertus 70B",
  human: "Mensch",
}

export interface Versions {
  model: string
  prompt: string
  registry: string
}

// Randspalte neben dem Text: je Label Name, Konfidenz, Zustand des Belegs, Prüfbedarf und, im
// Review-Modus, die Entscheide. Ein verworfenes Label bleibt sichtbar (durchgestrichen).
export function MarginNotes({
  affairId,
  labels,
  versions,
}: {
  affairId: string
  labels: MarginLabel[]
  versions: Versions
}) {
  const review = useReview()
  return (
    <aside
      aria-label="Labels dieses Geschäfts"
      className="flex flex-col gap-4 bg-margin-tint px-4 py-4 text-xs lg:border-l lg:border-border"
    >
      <h2 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Labels
      </h2>
      <ul className="flex flex-col gap-4">
        {labels.map((label) => {
          const key = reviewKey(affairId, label.tagId)
          const entry = review.decisions[key]
          const rejected = entry?.decision === "rejected"
          return (
            <li key={label.tagId} className="flex flex-col gap-1">
              <p
                className={
                  rejected
                    ? "text-sm font-semibold text-muted-foreground line-through"
                    : "text-sm font-semibold text-foreground"
                }
              >
                {label.name}
              </p>
              <Confidence value={label.confidence} />
              {label.evidence === null ? (
                <p className="text-muted-foreground">Kein Beleg angegeben</p>
              ) : label.evidenceFound ? (
                <p className="text-level-high">
                  <a
                    href={`#evidence-${label.tagId}`}
                    className="underline underline-offset-2"
                  >
                    Beleg im Text gefunden
                  </a>
                </p>
              ) : (
                <p className="font-semibold text-level-medium">
                  Beleg nicht im Text gefunden
                </p>
              )}
              {entry ? (
                <p
                  className={
                    rejected
                      ? "font-semibold text-level-low"
                      : "font-semibold text-level-high"
                  }
                >
                  {rejected ? "Verworfen" : "Bestätigt"} von {entry.by}
                </p>
              ) : (
                label.needsReview && (
                  <p className="font-semibold text-level-medium">Prüfung nötig</p>
                )
              )}
              <p className="text-muted-foreground">{STAGE_NAME[label.stage]}</p>
              {review.active && (
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {entry ? (
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => review.undo(key)}
                    >
                      Rückgängig
                    </Button>
                  ) : (
                    <>
                      <Button
                        size="xs"
                        onClick={() => review.decide(key, "confirmed")}
                      >
                        Bestätigen
                      </Button>
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => review.decide(key, "rejected")}
                      >
                        Verwerfen
                      </Button>
                    </>
                  )}
                </div>
              )}
            </li>
          )
        })}
      </ul>
      <details className="border-t border-border pt-3 text-muted-foreground">
        <summary className="cursor-pointer underline-offset-2 hover:underline">
          Technische Angaben
        </summary>
        <dl className="mt-2 flex flex-col gap-1.5">
          <div>
            <dt>Modell</dt>
            <dd className="tabular break-all text-foreground">{versions.model}</dd>
          </div>
          <div>
            <dt>Prompt</dt>
            <dd className="tabular text-foreground">{versions.prompt}</dd>
          </div>
          <div>
            <dt>Registry</dt>
            <dd className="tabular text-foreground">{versions.registry}</dd>
          </div>
        </dl>
      </details>
    </aside>
  )
}
