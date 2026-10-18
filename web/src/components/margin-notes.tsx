import { Confidence } from "@/components/confidence"
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

// Randspalte neben dem Text: je Label Name, Konfidenz, Zustand des Belegs und, was Prüfung braucht.
export function MarginNotes({
  labels,
  versions,
}: {
  labels: MarginLabel[]
  versions: Versions
}) {
  return (
    <aside
      aria-label="Labels dieses Geschäfts"
      className="flex flex-col gap-4 bg-margin-tint px-4 py-4 text-xs lg:border-l lg:border-border"
    >
      <h2 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Labels
      </h2>
      <ul className="flex flex-col gap-4">
        {labels.map((label) => (
          <li key={label.tagId} className="flex flex-col gap-1">
            <p className="text-sm font-semibold text-foreground">{label.name}</p>
            <Confidence value={label.confidence} />
            {label.evidence === null ? (
              <p className="text-muted-foreground">Kein Beleg angegeben</p>
            ) : label.evidenceFound ? (
              <p className="text-level-high">
                <a href={`#evidence-${label.tagId}`} className="underline underline-offset-2">
                  Beleg im Text gefunden
                </a>
              </p>
            ) : (
              <p className="font-semibold text-level-medium">Beleg nicht im Text gefunden</p>
            )}
            {label.needsReview && (
              <p className="font-semibold text-level-medium">Prüfung nötig</p>
            )}
            <p className="text-muted-foreground">{STAGE_NAME[label.stage]}</p>
          </li>
        ))}
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
