// Typen und Aufrufe der Sidecar-API (PRD 7.5, F10). Die Web-App spricht nur mit dem eigenen Host.

export type PageKind = "heart" | "bereich" | "kapitel" | "tag" | "querschnitt"

export interface WikiPage {
  page_id: string
  kind: PageKind
  title: string
  path: string
  parent_id: string | null
  linked_from: string[]
}

export interface PageTree {
  registry_version: string
  pages: WikiPage[]
}

export interface Health {
  status: string
  version: string
}

export async function fetchJson<T>(
  path: string,
  signal?: AbortSignal
): Promise<T> {
  const response = await fetch(path, {
    signal,
    headers: { Accept: "application/json" },
  })
  if (!response.ok) {
    throw new Error(await errorDetail(response))
  }
  return (await response.json()) as T
}

export async function postJson<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal
): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    signal,
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(await errorDetail(response))
  }
  return (await response.json()) as T
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (
      body !== null &&
      typeof body === "object" &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      return body.detail
    }
  } catch {
    // Antwort ohne JSON, z. B. vom Vite-Proxy, wenn die API nicht läuft.
  }
  return `HTTP ${response.status} ${response.statusText}`.trim()
}

// Antworten der Sidecar-API für Geschäfte, Themen und Jobs (siehe /v1/docs).
export type Stage = "8b" | "70b" | "human"

export type ReviewStatus = "confirmed" | "rejected" | "changed"

export interface TopicOut {
  tag_id: string
  scheme: "aps" | "adhoc"
  status: string
  parent_id: string | null
  name_de: string
  name_fr: string | null
  name_it: string | null
  n_affairs: number
}

export interface TopicAffair {
  affair_id: number
  body_key: string
  body_name: string | null
  body_level: string | null
  number: string | null
  title: string | null
  type: string | null
  /** Deutsche Bezeichnung der Geschäftsart, von der API geliefert. */
  type_de?: string | null
  begin_date: string | null
  /** Thema, zu dem diese Zeile gehört (bei Seitenabfragen mit mehreren Themen). */
  tag_id?: string
  name_de?: string
  confidence: number
  evidence: string | null
  evidence_verified: boolean
  stage: Stage
}

export interface TopicAffairs {
  total: number
  limit: number
  offset: number
  items: TopicAffair[]
}

export interface LabelOut {
  id: number
  tag_id: string
  name_de: string
  scheme: "aps" | "adhoc"
  confidence: number
  evidence: string | null
  evidence_verified: boolean
  status: "active" | "rejected" | "superseded"
  review_status: ReviewStatus | null
  reviewed_by: string | null
  reviewed_at: string | null
  task: string
  stage: Stage
  model_version: string
  prompt_version: string
  registry_version: string
  created_at: string
}

export interface AffairTopics {
  affair_id: number
  body_key: string
  body_name: string | null
  body_level: string | null
  number: string | null
  title: string | null
  type: string | null
  type_de: string | null
  begin_date: string | null
  url_external: string | null
  text: string | null
  language: string | null
  summary_de: string | null
  labels: LabelOut[]
}

export interface JobCounts {
  task: string
  open: number
  pending: number
  done: number
  failed: number
  total: number
}

export interface JobsSummary {
  tasks: JobCounts[]
}

export interface BodyOut {
  body_key: string
  name: string | null
  level: string | null
  n_affairs: number
}

/** Grund, warum ein Label in der Warteschlange steht (Codes der API, Text in lib/label-state.ts). */
export type ReviewReason =
  | "low_confidence"
  | "no_evidence"
  | "evidence_unverified"
  | "sample"

/** Kopf eines Geschäfts, wie ihn Listen der API tragen. */
export interface AffairHead {
  affair_id: number
  body_key: string
  body_name: string | null
  body_level: string | null
  number: string | null
  title: string | null
  type: string | null
  type_de: string | null
  begin_date: string | null
}

export interface ReviewItem extends AffairHead {
  label: LabelOut
  reasons: ReviewReason[]
}

export interface ReviewQueue {
  /** CONFIDENCE_THRESHOLD der Klassifikation; darunter gilt eine Konfidenz als tief. */
  threshold: number
  total: number
  limit: number
  offset: number
  items: ReviewItem[]
}

export type ReviewAction = "confirm" | "reject" | "change" | "add" | "undo"

export interface ReviewIn {
  affair_id: number
  tag_id: string
  action: ReviewAction
  new_tag_id?: string
  comment?: string
  user_name: string
}

/** Ein aktives Thema eines Suchtreffers mit seinem Beleg. */
export interface HitTopic {
  tag_id: string
  name_de: string
  confidence: number
  evidence: string | null
  evidence_verified: boolean
  stage: Stage
}

export interface SearchHit extends AffairHead {
  /** null ohne Suchbegriff (neueste Geschäfte). */
  rank: number | null
  /** Ausschnitt als HTML: alles maskiert, nur Treffer in <mark>. Nie ungeprüft einfügen. null ohne q. */
  headline: string | null
  topics: HitTopic[]
}

export interface SearchResult {
  /** null: Liste der neuesten Geschäfte statt einer Suche. */
  q: string | null
  total: number
  limit: number
  offset: number
  duration_ms: number
  items: SearchHit[]
}
