import { useState, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useReview } from "@/hooks/use-review"

// Anmeldung für den Review, einmal oben auf der Seite "Review". Der Token schaltet nur die Knöpfe
// frei; geprüft wird er vom Server (REVIEW_TOKEN), sobald es den Endpunkt gibt. Das Passwortfeld
// hält ihn aus Screenshots und Videos heraus.
export function ReviewSignIn() {
  const review = useReview()
  const [name, setName] = useState("")
  const [token, setToken] = useState("")
  const [error, setError] = useState("")

  if (review.active) {
    return (
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span>
          Angemeldet als{" "}
          <strong className="font-semibold">{review.name}</strong>
        </span>
        <Button size="xs" variant="outline" onClick={review.deactivate}>
          Abmelden
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
    <form
      onSubmit={submit}
      aria-label="Anmeldung für den Review"
      className="flex max-w-xl flex-col gap-2 text-sm"
    >
      <p className="text-muted-foreground">
        Zum Entscheiden anmelden. Den Token bekommst du vom Team.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex min-w-40 flex-1 flex-col gap-1 text-xs">
          Dein Name
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoComplete="name"
          />
        </label>
        <label className="flex min-w-40 flex-1 flex-col gap-1 text-xs">
          Token
          <Input
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            autoComplete="off"
          />
        </label>
        <Button type="submit" size="sm">
          Anmelden
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </form>
  )
}
