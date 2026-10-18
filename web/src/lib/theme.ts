// Darstellung: "auto" folgt der Geräteeinstellung, sonst gilt die Wahl. Das Ergebnis steht als
// data-theme am <html>; das Skript in index.html setzt es schon vor dem ersten Zeichnen.
export type ThemeChoice = "auto" | "light" | "dark"

const KEY = "parltopics-theme"

export const THEME_CHOICES: { value: ThemeChoice; label: string }[] = [
  { value: "auto", label: "Automatisch" },
  { value: "light", label: "Hell" },
  { value: "dark", label: "Dunkel" },
]

export function readTheme(): ThemeChoice {
  try {
    const saved = localStorage.getItem(KEY)
    return saved === "light" || saved === "dark" ? saved : "auto"
  } catch {
    return "auto"
  }
}

export function saveTheme(choice: ThemeChoice): void {
  try {
    if (choice === "auto") localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, choice)
  } catch {
    // Ohne Speicher gilt die Wahl nur bis zum Neuladen.
  }
}

export function applyTheme(choice: ThemeChoice): void {
  const dark =
    choice === "dark" ||
    (choice === "auto" && matchMedia("(prefers-color-scheme: dark)").matches)
  document.documentElement.dataset.theme = dark ? "dark" : "light"
}
