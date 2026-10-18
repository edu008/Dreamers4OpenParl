// Schwelle aus der Klassifikation (CONFIDENCE_THRESHOLD, Startwert 0.6). Später aus der API.
export const REVIEW_BELOW = 0.6

export interface LabelFacts {
  confidence: number
  evidence: string | null
  evidenceVerified: boolean
}

/** Gründe, warum ein Label geprüft werden sollte. Leer heisst: kein Prüfbedarf. */
export function reviewReasons(label: LabelFacts): string[] {
  const reasons: string[] = []
  if (label.confidence < REVIEW_BELOW) reasons.push("Konfidenz unter 0.6")
  if (label.evidence === null) reasons.push("Kein Beleg angegeben")
  else if (!label.evidenceVerified) reasons.push("Beleg nicht im Text gefunden")
  return reasons
}
