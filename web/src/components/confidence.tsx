import { cn } from "cn"

// Stufen wie in der Klassifikation: ab 0.8 hoch, ab 0.6 mittel (Schwelle CONFIDENCE_THRESHOLD),
// darunter tief. Das Wort trägt die Bedeutung, die Farbe verstärkt sie nur.
export type ConfidenceLevel = "hoch" | "mittel" | "tief"

export function confidenceLevel(value: number): ConfidenceLevel {
  if (value >= 0.8) return "hoch"
  if (value >= 0.6) return "mittel"
  return "tief"
}

const LEVEL_CLASS: Record<ConfidenceLevel, string> = {
  hoch: "text-level-high",
  mittel: "text-level-medium",
  tief: "text-level-low",
}

export function Confidence({
  value,
  className,
}: {
  value: number
  className?: string
}) {
  const level = confidenceLevel(value)
  return (
    <span className={cn("inline-flex items-baseline gap-1.5", className)}>
      <span
        className={cn("tabular text-sm font-semibold", LEVEL_CLASS[level])}
        aria-label={`Konfidenz ${value.toFixed(2)}`}
      >
        {value.toFixed(2)}
      </span>
      <span className="text-xs text-muted-foreground">{level}</span>
    </span>
  )
}
