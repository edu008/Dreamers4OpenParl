// Aufrufe der Ad-hoc-Endpunkte (PRD 7.4, F8). Die Oberfläche legt Themen nur auf Anfrage an: ein
// Mensch gibt Name und Beschreibung ein, prüft die Stichwörter und löst dann den Lauf aus.

export interface Keywords {
  de: string[]
  fr: string[]
  it: string[]
}

export interface PreviewExample {
  affair_id: number
  number: string | null
  title: string | null
  body_name: string | null
  begin_date: string | null
}

export interface AdhocPreview {
  /** Geschäfte mit Stichworttreffer. */
  candidates: number
  /** Stichprobe ohne Treffer, zur Kontrolle der Stichwortliste. */
  sample: number
  examples: PreviewExample[]
}

export interface AdhocScope {
  keywords: Keywords
  bodies?: string[] | null
  since?: string | null
}

export interface AdhocInput extends AdhocScope {
  name_de: string
  description_de: string
  broader: string[]
  user_name: string
}

export interface AdhocCreated {
  tag_id: string
  registry_version: string
  run_id: number
  jobs: number
  candidates: number
  sample: number
}

export interface AdhocActivated {
  tag_id: string
  status: "active"
  registry_version: string
}

/** Ein Stichwort je Zeile, ohne Leerzeilen und Doppelte. */
export function toTerms(text: string): string[] {
  return [
    ...new Set(
      text
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
    ),
  ]
}

export function termCount(keywords: Keywords): number {
  return keywords.de.length + keywords.fr.length + keywords.it.length
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

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  })
  if (!response.ok)
    throw new HttpError(response.status, await detailOf(response))
  return (await response.json()) as T
}

export class HttpError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Apertus 70B schlägt Stichwörter in de, fr und it vor; ein Mensch prüft sie. */
export function suggestKeywords(name: string, description: string) {
  return postJson<Keywords>("/v1/adhoc/keywords", {
    name_de: name,
    description_de: description,
  })
}

/** Zählt Kandidaten und Stichprobe, ohne etwas anzulegen und ohne Modell. */
export function previewAdhoc(scope: AdhocScope) {
  return postJson<AdhocPreview>("/v1/adhoc/preview", scope)
}

/** Legt das Thema als «proposed» an und öffnet die Läufe für Kandidaten und Stichprobe. */
export function createAdhoc(input: AdhocInput) {
  return postJson<AdhocCreated>("/v1/adhoc", input)
}

/** Schaltet ein bewährtes Thema von «proposed» auf «active». */
export function activateAdhoc(tagId: string, userName: string) {
  return postJson<AdhocActivated>(
    `/v1/adhoc/${encodeURIComponent(tagId)}/activate`,
    { user_name: userName }
  )
}

export interface AdhocRetired {
  tag_id: string
  status: "retired"
  registry_version: string
  /** geschlossene Jobs, auch erledigte */
  jobs: number
  /** Labels ohne menschlichen Entscheid, jetzt superseded; geprüfte bleiben aktiv */
  labels: number
}

/** Rückweg zum Anlegen und Freischalten: setzt das Thema auf «retired». Gelöscht wird nichts. */
export function retireAdhoc(tagId: string, userName: string) {
  return postJson<AdhocRetired>(
    `/v1/adhoc/${encodeURIComponent(tagId)}/retire`,
    { user_name: userName }
  )
}
