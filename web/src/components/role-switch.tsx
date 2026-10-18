import { useReview } from "@/hooks/use-review"
import { ROLES } from "@/lib/review"

// Ansichtsschalter für die Demo: zeigt, was Leser und Admin sehen. Das MVP hat keine
// Zugangskontrolle, der Schalter ist eine Darstellung und kein Schutz. Bewusst dezent gehalten.
export function RoleSwitch() {
  const { role, setRole } = useReview()
  return (
    <div
      role="group"
      aria-label="Ansicht"
      title="Demo-Ansicht: was sieht ein Leser, was ein Admin?"
      className="inline-flex overflow-hidden rounded-md border border-border text-xs"
    >
      {ROLES.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={role === option.value}
          onClick={() => setRole(option.value)}
          className={
            role === option.value
              ? "bg-secondary px-3 py-2 font-medium text-foreground"
              : "bg-background px-3 py-2 text-muted-foreground hover:bg-muted hover:text-foreground"
          }
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
