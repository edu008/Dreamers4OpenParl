// Ansicht (Rolle) und Review-Entscheide. Das MVP hat keine Zugangskontrolle: die Ansicht ist eine
// Darstellung für die Demo, keine Berechtigung. Solange es keinen Endpunkt POST /v1/reviews gibt,
// gelten die Entscheide nur in diesem Browser.

export type Role = "leser" | "reviewer" | "admin"

export const ROLES: { value: Role; label: string }[] = [
  { value: "leser", label: "Leser" },
  { value: "reviewer", label: "Reviewer" },
  { value: "admin", label: "Admin" },
]

export type ReviewDecision = "confirmed" | "rejected"

export interface ReviewEntry {
  decision: ReviewDecision
  by: string
  at: string
}

export type ReviewMap = Record<string, ReviewEntry>

const ROLE_KEY = "parltopics-view-role"
const NAME_KEY = "parltopics-reviewer-name"
const DECISIONS_KEY = "parltopics-review-decisions"

export function reviewKey(affairId: string, tagId: string): string {
  return `${affairId}|${tagId}`
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Speicher gesperrt (privates Fenster): die Wahl gilt dann nur bis zum Neuladen.
  }
}

export function loadRole(): Role {
  const stored = read(ROLE_KEY)
  return ROLES.some((role) => role.value === stored)
    ? (stored as Role)
    : "leser"
}

export function saveRole(role: Role): void {
  write(ROLE_KEY, role)
}

export function loadName(): string {
  return read(NAME_KEY) ?? ""
}

export function saveName(name: string): void {
  write(NAME_KEY, name)
}

export function loadDecisions(): ReviewMap {
  try {
    const raw = read(DECISIONS_KEY)
    return raw === null ? {} : (JSON.parse(raw) as ReviewMap)
  } catch {
    return {}
  }
}

export function saveDecisions(decisions: ReviewMap): void {
  write(DECISIONS_KEY, JSON.stringify(decisions))
}
