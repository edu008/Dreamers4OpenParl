import { useState, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useReview } from "@/hooks/use-review"

// Review-Modus: Name und Token eingeben. Der Token schaltet nur die Knöpfe frei; geprüft wird er
// später vom Server (REVIEW_TOKEN). Ohne Token sind Entscheide nur lesbar.
export function ReviewBar() {
  const review = useReview()
  const [name, setName] = useState("")
  const [token, setToken] = useState("")
  const [error, setError] = useState("")

  if (review.active) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>
          Review-Modus:{" "}
          <strong className="font-semibold text-foreground">
            {review.name}
          </strong>
        </span>
        <Button size="xs" variant="outline" onClick={review.deactivate}>
          Beenden
        </Button>
      </div>
    )
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim() || !token.trim()) {
      setError("Name und Token eingeben")
      return
    }
    setError("")
    review.activate(name, token)
    setToken("")
  }

  return (
    <details className="relative text-xs">
      <summary className="cursor-pointer text-muted-foreground underline-offset-4 hover:underline">
        Review-Modus
      </summary>
      <form
        onSubmit={submit}
        className="absolute right-0 z-10 mt-2 flex w-64 flex-col gap-2 border border-border bg-background p-3"
      >
        <label className="flex flex-col gap-1">
          Dein Name
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoComplete="name"
          />
        </label>
        <label className="flex flex-col gap-1">
          Token
          <Input
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            autoComplete="off"
          />
        </label>
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" size="sm">
          Aktivieren
        </Button>
      </form>
    </details>
  )
}
