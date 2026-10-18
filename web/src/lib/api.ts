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
