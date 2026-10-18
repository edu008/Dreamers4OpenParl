// Ansicht (Rolle) und Name der prüfenden Person. Die Ansicht folgt der Adresse: / ist die öffentliche,
// rein lesende Seite, /admin der Bereich für Review und Verwaltung. Das MVP hat keine Zugangskontrolle:
// wer /admin aufruft, darf entscheiden. Die Entscheide speichert das Backend (POST /v1/reviews); der
// Browser merkt sich nur den Namen.

export type Role = "leser" | "admin"

export function isAdminPath(pathname: string): boolean {
  return pathname === "/admin" || pathname.startsWith("/admin/")
}

const NAME_KEY = "parltopics-reviewer-name"

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

export function loadName(): string {
  return read(NAME_KEY) ?? ""
}

export function saveName(name: string): void {
  write(NAME_KEY, name)
}
