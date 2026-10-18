import type { ReviewReason } from "@/lib/api"

export interface LabelFacts {
  confidence: number
  evidence: string | null
  evidenceVerified: boolean
}

/**
 * Gründe, warum ein Label geprüft werden sollte. Leer heisst: kein Prüfbedarf. Die Schwelle kommt
 * aus der API (`threshold` der Warteschlange); solange sie fehlt, zählt nur der Beleg.
 */
export function reviewReasons(
  label: LabelFacts,
  threshold: number | null
): ReviewReason[] {
  const reasons: ReviewReason[] = []
  if (threshold !== null && label.confidence < threshold) {
    reasons.push("low_confidence")
  }
  if (label.evidence === null) reasons.push("no_evidence")
  else if (!label.evidenceVerified) reasons.push("evidence_unverified")
  return reasons
}

export function reasonText(reason: ReviewReason, threshold: number): string {
  switch (reason) {
    case "low_confidence":
      return `Konfidenz unter ${threshold}`
    case "no_evidence":
      return "Kein Beleg angegeben"
    case "evidence_unverified":
      return "Beleg nicht im Text gefunden"
    case "sample":
      return "Stichprobe"
  }
}
