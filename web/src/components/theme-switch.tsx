import { useEffect, useState } from "react"

import {
  applyTheme,
  readTheme,
  saveTheme,
  THEME_CHOICES,
  type ThemeChoice,
} from "@/lib/theme"

// Leiser Schalter im Seitenfuss. "Automatisch" folgt der Geräteeinstellung, auch wenn sie sich
// während der Sitzung ändert.
export function ThemeSwitch() {
  const [choice, setChoice] = useState<ThemeChoice>(readTheme)

  useEffect(() => {
    applyTheme(choice)
    if (choice !== "auto") return
    const query = matchMedia("(prefers-color-scheme: dark)")
    const follow = () => applyTheme("auto")
    query.addEventListener("change", follow)
    return () => query.removeEventListener("change", follow)
  }, [choice])

  const choose = (next: ThemeChoice) => {
    saveTheme(next)
    setChoice(next)
  }

  return (
    <div
      role="group"
      aria-label="Darstellung"
      className="flex items-center gap-1"
    >
      <span className="mr-1 text-muted-foreground">Darstellung:</span>
      {THEME_CHOICES.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={choice === option.value}
          onClick={() => choose(option.value)}
          className={
            choice === option.value
              ? "rounded-sm bg-secondary px-2 py-2 font-medium text-foreground"
              : "rounded-sm px-2 py-2 text-muted-foreground hover:bg-muted hover:text-foreground"
          }
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
