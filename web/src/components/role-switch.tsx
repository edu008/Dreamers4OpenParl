import { useReview } from "@/hooks/use-review"
import { ROLES } from "@/lib/review"

// Ansichtsschalter für die Demo: zeigt, was Leser, Reviewer und Admin sehen. Das MVP hat keine
// Zugangskontrolle, der Schalter ist eine Darstellung und kein Schutz.
export function RoleSwitch() {
  const { role, setRole } = useReview()
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span id="view-label">Ansicht</span>
      <div
        role="group"
        aria-labelledby="view-label"
        className="inline-flex overflow-hidden rounded-md border border-border"
      >
        {ROLES.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={role === option.value}
            onClick={() => setRole(option.value)}
            className={
              role === option.value
                ? "bg-primary px-2.5 py-1 font-medium text-primary-foreground"
                : "bg-background px-2.5 py-1 text-foreground hover:bg-muted"
            }
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}
