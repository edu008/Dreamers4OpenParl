// Ansicht (Rolle) und Name der prüfenden Person. Das MVP hat keine Zugangskontrolle: die Ansicht ist eine
// Darstellung für die Demo, keine Berechtigung. Die Entscheide selbst speichert das Backend
// (POST /v1/reviews); der Browser merkt sich nur Ansicht und Name.

export type Role = "leser" | "admin"

export const ROLES: { value: Role; label: string }[] = [
  { value: "leser", label: "Leser" },
  { value: "admin", label: "Admin" },
]

const ROLE_KEY = "parltopics-view-role"
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

export function loadRole(): Role {
  const stored = read(ROLE_KEY)
  // Die frühere Ansicht «Reviewer» gibt es nicht mehr; Admin darf auch entscheiden.
  if (stored === "reviewer") return "admin"
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
