import { Segmented } from "@/components/segmented"
import { useReview } from "@/hooks/use-review"
import { ROLES } from "@/lib/review"

// Ansichtsschalter für die Demo: zeigt, was Leser, Reviewer und Admin sehen. Das MVP hat keine
// Zugangskontrolle, der Schalter ist eine Darstellung und kein Schutz. Bewusst dezent gehalten.
export function RoleSwitch() {
  const { role, setRole } = useReview()
  return (
    <Segmented
      label="Ansicht"
      title="Demo-Ansicht: was sieht ein Leser, Reviewer oder Admin?"
      options={ROLES}
      value={role}
      onChange={setRole}
    />
  )
}
