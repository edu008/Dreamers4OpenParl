import { Input } from "@/components/ui/input"
import { useReview } from "@/hooks/use-review"

// Freiwilliger Name, damit bei jedem Entscheid steht, wer ihn getroffen hat. Kein Login.
export function ReviewerName() {
  const { name, setName } = useReview()
  return (
    <label className="flex max-w-xs flex-col gap-1 text-xs text-muted-foreground">
      Dein Name (freiwillig, erscheint bei deinen Entscheiden)
      <Input
        value={name}
        onChange={(event) => setName(event.target.value)}
        autoComplete="name"
      />
    </label>
  )
}
