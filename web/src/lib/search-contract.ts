import type { Stage } from "@/lib/api"

// Erwartete Antwort der Suche. Die Suche in ganzen Sätzen übernimmt ein Agent im Backend; die
// Oberfläche zeigt nur an, was er liefert. Bis der Endpunkt (z. B. POST /v1/agent/search) existiert,
// ist die Seite "Suche" ein Platzhalter. Diese Typen beschreiben, was die Oberfläche braucht.

/** Ein Thema, mit dem ein Treffer verknüpft ist, samt Beleg. */
export interface HitTopic {
  tag_id: string
  name: string
  confidence: number
  evidence: string | null
  evidence_verified: boolean
  stage: Stage
}

/** Ein Geschäft als Treffer. */
export interface SearchHit {
  affair_id: number
  number: string | null
  type: string | null
  title: string
  body_name: string | null
  body_key: string
  begin_date: string | null
  topics: HitTopic[]
}

export interface SearchResponse {
  query: string
  /** Kurzantwort, nur aus Werkzeug-Ergebnissen belegt; null, wenn es keine Treffer gibt. */
  answer: string | null
  hits: SearchHit[]
  /** Themen, die zum Suchweg gehören oder verwandt sind (für Verknüpfungen). */
  related_topics: { tag_id: string; name: string }[]
  /** Suchweg durch den Seitenbaum, damit der Nutzer nachvollziehen kann, wie gesucht wurde. */
  path: { page_id: string; title: string }[]
}
