import { XIcon } from "lucide-react"
import { Fragment, useEffect, useRef, useState } from "react"
import { Link } from "react-router"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useQuery } from "@/hooks/use-query"
import { postJson, type AgentResult } from "@/lib/api"

export interface Asked {
  question: string
  result?: AgentResult
  error?: string
}

const STATUS_NOTE: Record<AgentResult["status"], string | null> = {
  ok: null,
  no_results: "Dazu gibt es keine passenden Geschäfte.",
  limit_reached:
    "Die Antwort ist unvollständig: Die Suche hat ihre Zeit- oder Schrittgrenze erreicht.",
}

function formatDate(iso: string | null): string {
  if (!iso) return ""
  const [year, month, day] = iso.slice(0, 10).split("-")
  return `${day}.${month}.${year}`
}

/** Eine Frage an den Agenten (POST /v1/agent/search). Ausgelöst vom Knopf, nicht von einem
 * Effekt: jede Frage kostet bis zu einer Minute Modellzeit und darf nicht doppelt starten. */
export function useAgent() {
  const [asked, setAsked] = useState<Asked | null>(null)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])

  function ask(question: string) {
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    setAsked({ question })
    postJson<AgentResult>(
      "/v1/agent/search",
      { query: question },
      current.signal
    ).then(
      (result) => setAsked({ question, result }),
      (error: unknown) => {
        if (current.signal.aborted) return
        const message = error instanceof Error ? error.message : String(error)
        setAsked({ question, error: message })
      }
    )
  }

  function close() {
    controller.current?.abort()
    setAsked(null)
  }

  const asking = asked !== null && !asked.result && !asked.error
  return { asked, ask, close, asking }
}

function Waiting({ onCancel }: { onCancel: () => void }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000)
    return () => clearInterval(timer)
  }, [])
  return (
    <div className="flex flex-col gap-3">
      <p>
        Die Antwort wird aus den Geschäften zusammengestellt.{" "}
        <span aria-hidden className="tabular text-muted-foreground">
          {seconds} s
        </span>
      </p>
      <p className="text-sm text-muted-foreground">
        Das dauert bis zu einer Minute.
      </p>
      <div aria-hidden className="flex max-w-[68ch] flex-col gap-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-11/12" />
        <Skeleton className="h-4 w-2/3" />
      </div>
      <Button variant="outline" className="self-start" onClick={onCancel}>
        Abbrechen
      </Button>
    </div>
  )
}

// Antwort auf eine Frage: Text mit nummerierten Belegen, darunter die Quellen. Ein Beleg öffnet
// das Geschäft als Pop-up, wie in der Trefferliste. Einen Themen-Entwurf des Agenten zeigt die
// öffentliche Seite nicht: neue Themen legt ein Mensch im Admin an.
export function AgentAnswer({
  asked,
  onClose,
}: {
  asked: Asked
  onClose: () => void
}) {
  const [params] = useQuery()
  const { result, error } = asked
  const order = result?.cited_affair_ids ?? []
  const hits = new Map(result?.hits.map((hit) => [hit.affair_id, hit]))
  const note = result && STATUS_NOTE[result.status]

  function popup(id: number) {
    const next = new URLSearchParams(params)
    next.set("geschaeft", String(id))
    return { search: `?${next}` }
  }

  return (
    <section
      aria-labelledby="answer-heading"
      className="flex flex-col gap-5 border-l-4 border-foreground bg-muted p-5 sm:p-7"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <h2 id="answer-heading" className="text-lg font-bold">
            Antwort
          </h2>
          <p className="text-sm break-words text-muted-foreground">
            «{asked.question}»
          </p>
        </div>
        <Button
          variant="outline"
          size="icon"
          title="Antwort schliessen"
          onClick={onClose}
        >
          <XIcon className="size-5" />
          <span className="sr-only">Antwort schliessen</span>
        </Button>
      </div>

      <div aria-live="polite" className="flex flex-col gap-5">
        {!result && !error && <Waiting onCancel={onClose} />}
        {error && (
          <p className="max-w-[68ch]">
            Die Frage konnte nicht beantwortet werden ({error}). Die Suche nach
            Stichwörtern funktioniert weiter.
          </p>
        )}
        {result?.answer && (
          <p className="max-w-[68ch] text-lg leading-relaxed whitespace-pre-line">
            {/* Belege «[70435]» oder «[70435, 70437]» werden zu hochgestellten Nummern. */}
            {result.answer.split(/(\[[\d,\s]+\])/).map((part, index) => {
              if (index % 2 === 0) return part
              const ids = part
                .slice(1, -1)
                .split(",")
                .map(Number)
                .filter((id) => order.includes(id))
              if (ids.length === 0) return part
              return (
                <sup key={index} className="ml-0.5 text-xs font-bold">
                  {ids.map((id, position) => (
                    <Fragment key={id}>
                      {position > 0 && ","}
                      <Link
                        to={popup(id)}
                        state={{ popup: true }}
                        aria-label={`Quelle ${order.indexOf(id) + 1}`}
                        className="underline-offset-2 hover:text-primary hover:underline"
                      >
                        {order.indexOf(id) + 1}
                      </Link>
                    </Fragment>
                  ))}
                </sup>
              )
            })}
          </p>
        )}
        {note && <p className="font-bold">{note}</p>}
        {order.length > 0 && (
          <div className="flex flex-col gap-2">
            <h3 className="text-base font-bold">Quellen</h3>
            <ol>
              {order.map((id, index) => {
                const hit = hits.get(id)
                if (!hit) return null
                const meta = [
                  hit.type_de ?? hit.type,
                  hit.number && `Nr. ${hit.number}`,
                  hit.body_name ?? hit.body_key,
                  formatDate(hit.begin_date),
                ]
                return (
                  <li
                    key={id}
                    className="grid grid-cols-[2rem_minmax(0,1fr)] border-t border-border py-3 first:border-t-0"
                  >
                    <span className="tabular text-sm font-bold">
                      {index + 1}
                    </span>
                    <div className="flex min-w-0 flex-col gap-1">
                      <Link
                        to={popup(id)}
                        state={{ popup: true }}
                        className="leading-snug font-bold underline-offset-4 hover:text-primary hover:underline"
                      >
                        {hit.title ?? `Geschäft ${id}`}
                      </Link>
                      <p className="tabular text-sm text-muted-foreground">
                        {meta.filter(Boolean).join(" · ")}
                      </p>
                    </div>
                  </li>
                )
              })}
            </ol>
          </div>
        )}
        {result && (
          <p className="text-sm text-muted-foreground">
            Automatisch aus den genannten Geschäften zusammengestellt, ohne
            Wertung. Bitte die Quellen prüfen.
          </p>
        )}
      </div>
    </section>
  )
}
