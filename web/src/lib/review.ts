// Review-Entscheide (Human in the loop). Solange es keinen Endpunkt POST /v1/reviews gibt, gelten
// die Entscheide nur in diesem Browser (Beispieldaten). Der Token bleibt in der Sitzung.

export type ReviewDecision = "confirmed" | "rejected"

export interface ReviewEntry {
  decision: ReviewDecision
  by: string
  at: string
}

export type ReviewMap = Record<string, ReviewEntry>

const SESSION_KEY = "parltopics-review-session"
const DECISIONS_KEY = "parltopics-review-decisions"

export interface ReviewSession {
  name: string
  token: string
}

export function reviewKey(affairId: string, tagId: string): string {
  return `${affairId}|${tagId}`
}

function read<T>(storage: Storage, key: string): T | null {
  try {
    const raw = storage.getItem(key)
    return raw === null ? null : (JSON.parse(raw) as T)
  } catch {
    return null
  }
}

function write(storage: Storage, key: string, value: unknown): void {
  try {
    storage.setItem(key, JSON.stringify(value))
  } catch {
    // Speicher gesperrt (privates Fenster): der Entscheid gilt dann nur bis zum Neuladen.
  }
}

export function loadSession(): ReviewSession | null {
  return read<ReviewSession>(sessionStorage, SESSION_KEY)
}

export function saveSession(session: ReviewSession | null): void {
  if (session === null) {
    try {
      sessionStorage.removeItem(SESSION_KEY)
    } catch {
      // nichts zu tun
    }
    return
  }
  write(sessionStorage, SESSION_KEY, session)
}

export function loadDecisions(): ReviewMap {
  return read<ReviewMap>(localStorage, DECISIONS_KEY) ?? {}
}

export function saveDecisions(decisions: ReviewMap): void {
  write(localStorage, DECISIONS_KEY, decisions)
}
