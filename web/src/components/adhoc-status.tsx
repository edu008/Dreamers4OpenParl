import { useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { useApi } from "@/hooks/use-api"
import { useReview } from "@/hooks/use-review"
import { activateAdhoc, retireAdhoc, type AdhocRetired } from "@/lib/adhoc"
import type { TopicOut } from "@/lib/api"

// Stand eines Ad-hoc-Themas auf seiner Seite: vorläufig (freischalten oder zurückziehen) oder
// aktiv (zurückziehen). Zurückziehen fragt einmal nach, weil es die Jobs schliesst und die
// ungeprüften Labels ersetzt; gelöscht wird nichts.
export function AdhocStatus({ tagId }: { tagId: string }) {
  const topics = useApi<TopicOut[]>("/v1/topics?scheme=adhoc")
  const { name } = useReview()
  const [busy, setBusy] = useState(false)
  const [activated, setActivated] = useState(false)
  const [retired, setRetired] = useState<AdhocRetired>()
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string>()
  const topic = topics.data?.find((candidate) => candidate.tag_id === tagId)
  const userName = name.trim() || "Admin"

  if (retired) {
    return (
      <p role="status" className="text-sm text-muted-foreground">
        Das Thema ist zurückgezogen. {retired.jobs} Jobs geschlossen,{" "}
        {retired.labels} ungeprüfte Labels ersetzt; geprüfte bleiben.
      </p>
    )
  }
  if (!topic || (topic.status !== "proposed" && topic.status !== "active")) {
    return null
  }
  const proposed = topic.status === "proposed" && !activated

  async function run(step: () => Promise<void>) {
    setBusy(true)
    setError(undefined)
    try {
      await step()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    } finally {
      setBusy(false)
      setConfirming(false)
    }
  }

  return (
    <Alert>
      <AlertTitle>{proposed ? "Vorläufiges Thema" : "Ad-hoc-Thema"}</AlertTitle>
      <AlertDescription className="flex flex-col gap-2">
        <span>
          {proposed
            ? "Dieses Thema ist noch nicht freigegeben. Die Treffer stammen aus der Stichwortsuche und einer Stichprobe und sind noch nicht von einem Menschen geprüft."
            : "Das Thema ist freigegeben und läuft im täglichen Lauf mit."}
        </span>
        <span className="flex flex-wrap items-center gap-3">
          {proposed && !confirming && (
            <Button
              size="sm"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  await activateAdhoc(tagId, userName)
                  setActivated(true)
                })
              }
            >
              {busy ? "Läuft …" : "Thema freischalten"}
            </Button>
          )}
          {confirming ? (
            <>
              <span className="text-xs">
                Jobs schliessen und ungeprüfte Labels ersetzen?
              </span>
              <Button
                size="sm"
                variant="destructive"
                disabled={busy}
                onClick={() =>
                  run(async () =>
                    setRetired(await retireAdhoc(tagId, userName))
                  )
                }
              >
                {busy ? "Läuft …" : "Ja, zurückziehen"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => setConfirming(false)}
              >
                Abbrechen
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => setConfirming(true)}
            >
              Thema zurückziehen
            </Button>
          )}
        </span>
        {error && (
          <span role="alert" className="text-xs text-destructive">
            Nicht ausgeführt: {error}
          </span>
        )}
      </AlertDescription>
    </Alert>
  )
}
