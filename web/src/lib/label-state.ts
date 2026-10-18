import { isEvidenceFound } from "@/components/evidence-text"
import type { AffairLabel, AffairRecord } from "@/lib/sample-affairs"

// Schwelle aus der Klassifikation (CONFIDENCE_THRESHOLD, Startwert 0.6). Später aus der API.
export const REVIEW_BELOW = 0.6

export function evidenceFound(
  affair: AffairRecord,
  label: AffairLabel
): boolean {
  return (
    label.evidence !== null &&
    isEvidenceFound(affair.paragraphs, label.evidence)
  )
}

/** Gründe, warum ein Label geprüft werden sollte. Leer heisst: kein Prüfbedarf. */
export function reviewReasons(
  affair: AffairRecord,
  label: AffairLabel
): string[] {
  const reasons: string[] = []
  if (label.confidence < REVIEW_BELOW) reasons.push("Konfidenz unter 0.6")
  if (label.evidence === null) reasons.push("Kein Beleg angegeben")
  else if (!evidenceFound(affair, label))
    reasons.push("Beleg nicht im Text gefunden")
  return reasons
}
