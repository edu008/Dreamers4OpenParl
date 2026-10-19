import { useState } from "react"
import { Link } from "react-router"

import { Confidence } from "@/components/confidence"
import { TopicPicker } from "@/components/topic-picker"
import { Button } from "@/components/ui/button"
import { useReview } from "@/hooks/use-review"
import type { LabelOut, Stage, TopicOut } from "@/lib/api"

export interface MarginLabel {
  id: number
  tagId: string
  name: string
  confidence: number
  evidence: string | null
  stage: Stage
  /** Der Server hat die Textstelle im Text gefunden (evidence_verified). */
  evidenceVerified: boolean
  /** Die Textstelle lässt sich im Text markieren (wörtliche Übereinstimmung). */
  evidenceMarked: boolean
  needsReview: boolean
  /** Der Backend-Zustand des Labels: verworfene bleiben sichtbar, durchgestrichen. */
  status: LabelOut["status"]
  reviewStatus: LabelOut["review_status"]
  reviewedBy: string | null
}

const DECISION_NAME = {
  confirmed: "Bestätigt",
  rejected: "Verworfen",
  changed: "Geändert",
} as const

const STAGE_NAME: Record<Stage, string> = {
  "8b": "Apertus 8B",
  "70b": "Apertus 70B",
  human: "Mensch",
  rule: "Regel",
}

export interface Versions {
  model: string
  prompt: string
  registry: string
}

// Randspalte neben dem Text: je Label Name, Konfidenz, Zustand des Belegs, Prüfbedarf und, in
// der Prüfansicht, die Entscheide. Ein verworfenes Label bleibt sichtbar (durchgestrichen).
export function MarginNotes({
  mode,
  labels,
  versions,
  pendingId,
  error,
  onDecide,
  topics,
  onChange,
  onAdd,
}: {
  mode: "public" | "review"
  labels: MarginLabel[]
  versions: Versions | null
  /** Label, dessen Entscheid gerade gespeichert wird. */
  pendingId: number | null
  error: string | undefined
  onDecide: (label: MarginLabel, action: "confirm" | "reject" | "undo") => void
  /** Alle Themen der Registry, für «Ersetzen» und «Thema ergänzen» (nur in der Prüfansicht). */
  topics?: TopicOut[]
  onChange?: (label: MarginLabel, newTagId: string) => void
  onAdd?: (tagId: string) => void
}) {
  const review = useReview()
  const [replacing, setReplacing] = useState<number | null>(null)
  const [replacement, setReplacement] = useState("")
  const [addition, setAddition] = useState("")
  const taken = labels
    .filter((label) => label.status === "active")
    .map((label) => label.tagId)
  return (
    <aside
      aria-label="Labels dieses Geschäfts"
      className="flex flex-col gap-4 bg-muted p-5 text-xs"
    >
      <h2 className="text-base font-semibold">Themen</h2>
      {labels.length === 0 && (
        <p className="text-muted-foreground">Noch kein Label vergeben.</p>
      )}
      <ul className="flex flex-col gap-4">
        {labels.map((label) => {
          const decided = label.reviewStatus !== null
          const rejected = label.status === "rejected"
          const busy = pendingId === label.id
          return (
            <li key={label.id} className="flex flex-col gap-1">
              <p
                className={
                  rejected
                    ? "text-sm font-semibold text-muted-foreground line-through"
                    : "text-sm font-semibold text-foreground"
                }
              >
                {mode === "public" && !rejected ? (
                  // Öffentlich führt ein Thema zur Suche mit diesem Thema als Filter.
                  <Link
                    to={`/?thema=${encodeURIComponent(label.tagId)}`}
                    className="underline decoration-muted-foreground/50 underline-offset-4 hover:decoration-foreground"
                  >
                    {label.name}
                  </Link>
                ) : (
                  label.name
                )}
              </p>
              <Confidence value={label.confidence} labelled />
              {label.evidence === null ? (
                <p className="text-muted-foreground">Kein Beleg angegeben</p>
              ) : label.evidenceVerified ? (
                <p className="text-level-high">
                  {label.evidenceMarked ? (
                    <a
                      href={`#evidence-${label.tagId}`}
                      className="underline underline-offset-2"
                    >
                      Beleg im Text gefunden
                    </a>
                  ) : (
                    "Beleg im Text gefunden"
                  )}
                </p>
              ) : (
                <p className="font-semibold text-level-medium">
                  Beleg nicht im Text gefunden
                </p>
              )}
              {decided ? (
                <p
                  className={
                    rejected
                      ? "font-semibold text-level-low"
                      : "font-semibold text-level-high"
                  }
                >
                  {DECISION_NAME[label.reviewStatus ?? "confirmed"]} von{" "}
                  {label.reviewedBy}
                </p>
              ) : mode === "public" ? (
                <p className="text-muted-foreground">
                  Noch nicht von einem Menschen geprüft
                </p>
              ) : (
                label.needsReview && (
                  <p className="font-semibold text-level-medium">
                    Prüfung nötig
                  </p>
                )
              )}
              <p className="text-muted-foreground">{STAGE_NAME[label.stage]}</p>
              {mode === "review" && review.active && (
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {decided ? (
                    <Button
                      size="xs"
                      variant="outline"
                      disabled={busy}
                      onClick={() => onDecide(label, "undo")}
                    >
                      Rückgängig
                    </Button>
                  ) : (
                    <>
                      <Button
                        size="xs"
                        disabled={busy}
                        onClick={() => onDecide(label, "confirm")}
                      >
                        Bestätigen
                      </Button>
                      <Button
                        size="xs"
                        variant="outline"
                        disabled={busy}
                        onClick={() => onDecide(label, "reject")}
                      >
                        Verwerfen
                      </Button>
                      {topics && onChange && (
                        <Button
                          size="xs"
                          variant="outline"
                          disabled={busy}
                          onClick={() => {
                            setReplacing(replacing === label.id ? null : label.id)
                            setReplacement("")
                          }}
                        >
                          Ersetzen
                        </Button>
                      )}
                    </>
                  )}
                </div>
              )}
              {replacing === label.id && topics && onChange && (
                <div className="mt-2 flex flex-col gap-2 border-t border-border pt-2">
                  <TopicPicker
                    topics={topics}
                    excluded={taken}
                    value={replacement}
                    onChange={setReplacement}
                    label="Durch welches Thema ersetzen?"
                  />
                  <div className="flex gap-1.5">
                    <Button
                      size="xs"
                      disabled={busy || replacement === ""}
                      onClick={() => {
                        onChange(label, replacement)
                        setReplacing(null)
                      }}
                    >
                      Ersetzen
                    </Button>
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => setReplacing(null)}
                    >
                      Abbrechen
                    </Button>
                  </div>
                </div>
              )}
            </li>
          )
        })}
      </ul>
      {mode === "review" && review.active && topics && onAdd && (
        <details className="border-t border-border pt-3">
          <summary className="cursor-pointer font-semibold underline-offset-2 hover:underline">
            Thema ergänzen
          </summary>
          <div className="mt-2 flex flex-col gap-2">
            <TopicPicker
              topics={topics}
              excluded={taken}
              value={addition}
              onChange={setAddition}
              label="Welches Thema fehlt?"
            />
            <div>
              <Button
                size="xs"
                disabled={pendingId !== null || addition === ""}
                onClick={() => {
                  onAdd(addition)
                  setAddition("")
                }}
              >
                Thema ergänzen
              </Button>
            </div>
          </div>
        </details>
      )}
      {error && (
        <p role="alert" className="text-destructive">
          Entscheid nicht gespeichert: {error}
        </p>
      )}
      {versions && (
        <details className="border-t border-border pt-3 text-muted-foreground">
          <summary className="cursor-pointer underline-offset-2 hover:underline">
            Technische Angaben
          </summary>
          <dl className="mt-2 flex flex-col gap-1.5">
            <div>
              <dt>Modell</dt>
              <dd className="tabular break-all text-foreground">
                {versions.model}
              </dd>
            </div>
            <div>
              <dt>Prompt</dt>
              <dd className="tabular break-all text-foreground">
                {versions.prompt}
              </dd>
            </div>
            <div>
              <dt>Registry</dt>
              <dd className="tabular text-foreground">{versions.registry}</dd>
            </div>
          </dl>
        </details>
      )}
    </aside>
  )
}
