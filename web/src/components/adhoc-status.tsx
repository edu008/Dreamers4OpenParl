import { useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { useApi } from "@/hooks/use-api"
import { activateAdhoc } from "@/lib/adhoc"
import type { TopicOut } from "@/lib/api"

// Hinweis auf Seiten von Ad-hoc-Themen, die noch «vorläufig» sind: Die Treffer sind geprüft vom
// Modell, aber das Thema ist noch nicht freigegeben. Freischalten kann man in der Ansicht Admin.
export function AdhocStatus({ tagId }: { tagId: string }) {
  const topics = useApi<TopicOut[]>("/v1/topics?scheme=adhoc")
  const [busy, setBusy] = useState(false)
  const [activated, setActivated] = useState(false)
  const [error, setError] = useState<string>()
  const topic = topics.data?.find((candidate) => candidate.tag_id === tagId)

  if (activated) {
    return (
      <p role="status" className="text-sm text-muted-foreground">
        Das Thema ist freigegeben. Es läuft ab jetzt im täglichen Lauf mit.
      </p>
    )
  }
  if (!topic || topic.status !== "proposed") return null

  async function activate() {
    setBusy(true)
    setError(undefined)
    try {
      await activateAdhoc(tagId)
      setActivated(true)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Alert>
      <AlertTitle>Vorläufiges Thema</AlertTitle>
      <AlertDescription className="flex flex-col gap-2">
        <span>
          Dieses Thema ist noch nicht freigegeben. Die Treffer stammen aus der
          Stichwortsuche und einer Stichprobe und sind noch nicht von einem
          Menschen geprüft.
        </span>
        <span className="flex flex-wrap items-center gap-3">
          <Button size="sm" disabled={busy} onClick={activate}>
            {busy ? "Wird freigegeben …" : "Thema freischalten"}
          </Button>
          <span className="text-xs">
            Danach bietet das System es bei jedem Geschäft an.
          </span>
        </span>
        {error && (
          <span role="alert" className="text-xs text-destructive">
            Nicht freigegeben: {error}
          </span>
        )}
      </AlertDescription>
    </Alert>
  )
}
