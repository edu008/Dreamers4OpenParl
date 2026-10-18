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
  review_status: "confirmed" | "rejected" | "changed" | null
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
