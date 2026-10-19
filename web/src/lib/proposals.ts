// Tag-Vorschläge des Modells (PRD F7): Wo ein Thema fehlt, schlägt Apertus ein neues vor. Die
// Vorschläge werden gruppiert und auf Duplikate geprüft; ein Mensch nimmt an, legt zusammen oder
// lehnt ab. Angenommene Themen entstehen als «vorläufig» und werden erst später freigeschaltet.

export type Recommendation = "new" | "duplicate_of" | "child_of"
export type ProposalDecision = "accepted" | "merged" | "rejected"

export interface ProposalAffair {
  affair_id: number
  number: string | null
  title: string | null
  body_name: string | null
  begin_date: string | null
}

export interface Proposal {
  id: number
  name_de: string
  desc_de: string | null
  /** Begründung der Empfehlung. */
  reason: string | null
  recommendation: Recommendation | null
  related_tag_id: string | null
  related_name_de: string | null
  /** Namen der Rohvorschläge, höchstens fünf. */
  variants: string[]
  /** Geschäfte, bei denen das Modell das Thema vermisste. */
  n_affairs: number
  affairs: ProposalAffair[]
  status: "open" | "pending" | "done"
  decision: ProposalDecision | null
  decided_by: string | null
  decided_at: string | null
}

export interface ProposalList {
  total: number
  limit: number
  offset: number
  items: Proposal[]
}

export interface DecisionIn {
  decision: ProposalDecision
  user_name: string
  name_de?: string
  description_de?: string
  broader?: string[]
  related_tag_id?: string
}

export interface DecisionOut {
  proposal: Proposal
  tag_id: string | null
  run_id: number | null
  jobs: number | null
}

export const RECOMMENDATION_TEXT: Record<Recommendation, string> = {
  new: "Empfehlung: als neues Thema aufnehmen",
  duplicate_of: "Empfehlung: Duplikat eines vorhandenen Themas",
  child_of: "Empfehlung: Unterthema eines vorhandenen Themas",
}

export const DECISION_TEXT: Record<ProposalDecision, string> = {
  accepted: "Angenommen",
  merged: "Zusammengelegt",
  rejected: "Abgelehnt",
}

async function detailOf(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body !== null && typeof body === "object" && "detail" in body) {
      const detail = body.detail
      if (typeof detail === "string") return detail
      if (Array.isArray(detail)) return "Die Angaben sind nicht gültig."
    }
  } catch {
    // Antwort ohne JSON, z. B. vom Vite-Proxy, wenn die API nicht läuft.
  }
  return `HTTP ${response.status} ${response.statusText}`.trim()
}

export async function decideProposal(
  id: number,
  input: DecisionIn
): Promise<DecisionOut> {
  const response = await fetch(`/v1/proposals/${id}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(input),
  })
  if (!response.ok) throw new Error(await detailOf(response))
  return (await response.json()) as DecisionOut
}
