import { useState } from "react"
import { Link } from "react-router"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useApi } from "@/hooks/use-api"
import { useReview } from "@/hooks/use-review"
import type { TopicOut } from "@/lib/api"
import {
  decideProposal,
  DECISION_TEXT,
  RECOMMENDATION_TEXT,
  type Proposal,
  type ProposalDecision,
  type ProposalList,
} from "@/lib/proposals"

const TEXTAREA =
  "min-h-20 w-full rounded-md border border-input bg-transparent px-2.5 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

type Mode = "accept" | "merge" | null

function ProposalRow({
  proposal,
  topics,
  onDecided,
}: {
  proposal: Proposal
  topics: TopicOut[]
  onDecided: (message: string) => void
}) {
  const { name } = useReview()
  const [mode, setMode] = useState<Mode>(null)
  const [title, setTitle] = useState(proposal.name_de)
  const [description, setDescription] = useState(proposal.desc_de ?? "")
  const [target, setTarget] = useState(proposal.related_tag_id ?? "")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()

  async function decide(decision: ProposalDecision) {
    setBusy(true)
    setError(undefined)
    try {
      const result = await decideProposal(proposal.id, {
        decision,
        user_name: name.trim() || "Admin",
        ...(decision === "accepted"
          ? { name_de: title.trim(), description_de: description.trim() }
          : {}),
        ...(decision === "merged" ? { related_tag_id: target } : {}),
      })
      onDecided(
        decision === "accepted"
          ? `«${title.trim()}» angenommen. Das Thema ist vorläufig, ${result.jobs ?? 0} Geschäfte werden geprüft.`
          : decision === "merged"
            ? `«${proposal.name_de}» zusammengelegt.`
            : `«${proposal.name_de}» abgelehnt.`
      )
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
      setBusy(false)
    }
  }

  const acceptOk = title.trim().length >= 2 && description.trim().length >= 10

  return (
    <li className="flex flex-col gap-2 border-b border-border py-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="font-heading text-base font-semibold">
          {proposal.name_de}
        </h3>
        <span className="tabular text-xs text-muted-foreground">
          fehlt bei {proposal.n_affairs}{" "}
          {proposal.n_affairs === 1 ? "Geschäft" : "Geschäften"}
        </span>
      </div>
      {proposal.desc_de && (
        <p className="max-w-[68ch] text-sm text-muted-foreground">
          {proposal.desc_de}
        </p>
      )}
      {proposal.recommendation && (
        <p className="text-xs">
          <span className="font-semibold">
            {RECOMMENDATION_TEXT[proposal.recommendation]}
          </span>
          {proposal.related_name_de && <> «{proposal.related_name_de}»</>}
          {proposal.reason && (
            <span className="text-muted-foreground"> · {proposal.reason}</span>
          )}
        </p>
      )}
      {proposal.variants.length > 1 && (
        <p className="text-xs text-muted-foreground">
          Auch vorgeschlagen als: {proposal.variants.join(", ")}
        </p>
      )}
      {proposal.affairs.length > 0 && (
        <ul className="flex flex-col gap-0.5 text-xs text-muted-foreground">
          {proposal.affairs.slice(0, 3).map((affair) => (
            <li key={affair.affair_id}>
              {[affair.number, affair.body_name].filter(Boolean).join(" · ")}
              {": "}
              <Link
                to={`/geschaefte/${affair.affair_id}`}
                className="text-foreground underline underline-offset-2"
              >
                {affair.title ?? `Geschäft ${affair.affair_id}`}
              </Link>
            </li>
          ))}
        </ul>
      )}

      {mode === "accept" && (
        <div className="flex max-w-[68ch] flex-col gap-2 pt-1">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Name des Themas
            <Input
              value={title}
              maxLength={120}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Beschreibung (mindestens 10 Zeichen)
            <textarea
              className={TEXTAREA}
              value={description}
              maxLength={2000}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          <p className="text-xs text-muted-foreground">
            Das Thema entsteht als «vorläufig» und startet Läufe mit dem
            Sprachmodell für die betroffenen Geschäfte.
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={busy || !acceptOk}
              onClick={() => decide("accepted")}
            >
              {busy ? "Wird angelegt …" : "Als Ad-hoc-Thema anlegen"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setMode(null)}>
              Abbrechen
            </Button>
          </div>
        </div>
      )}

      {mode === "merge" && (
        <div className="flex max-w-[68ch] flex-col gap-2 pt-1">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            In welches Thema legen?
            <select
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              className="h-8 max-w-sm rounded-md border border-input bg-background px-2 text-sm text-foreground"
            >
              <option value="">Thema wählen</option>
              {topics.map((topic) => (
                <option key={topic.tag_id} value={topic.tag_id}>
                  {topic.name_de}
                </option>
              ))}
            </select>
          </label>
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={busy || target === ""}
              onClick={() => decide("merged")}
            >
              {busy ? "Wird gespeichert …" : "Zusammenlegen"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setMode(null)}>
              Abbrechen
            </Button>
          </div>
        </div>
      )}

      {mode === null && (
        <div className="flex flex-wrap gap-2 pt-1">
          <Button size="sm" onClick={() => setMode("accept")}>
            Annehmen
          </Button>
          <Button size="sm" variant="outline" onClick={() => setMode("merge")}>
            Zusammenlegen
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => decide("rejected")}
          >
            Ablehnen
          </Button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-xs text-destructive">
          Nicht gespeichert: {error}
        </p>
      )}
    </li>
  )
}

// Warteschlange der Tag-Vorschläge (F7): offene zuerst nach Zahl der betroffenen Geschäfte.
export function ProposalsPanel() {
  const [version, setVersion] = useState(0)
  const [notes, setNotes] = useState<string[]>([])
  const open = useApi<ProposalList>(`/v1/proposals?state=open&limit=50&v=${version}`)
  const done = useApi<ProposalList>(`/v1/proposals?state=done&limit=20&v=${version}`)
  const topics = useApi<TopicOut[]>("/v1/topics")

  if (open.loading) {
    return <p className="text-muted-foreground">Wird geladen …</p>
  }
  if (open.error || !open.data) {
    return (
      <p className="text-sm text-destructive">
        Vorschläge nicht geladen: {open.error}
      </p>
    )
  }
  const items = open.data.items
  const decided = done.data?.items ?? []

  return (
    <div className="flex flex-col gap-3">
      <p className="max-w-[68ch] text-sm text-muted-foreground">
        Wo kein vorhandenes Thema passt, schlägt das Modell beim Klassifizieren
        ein neues vor. Die Vorschläge sind gruppiert und auf Duplikate geprüft.
        Nichts wird ohne Entscheid eines Menschen aktiv.
      </p>
      {notes.map((note) => (
        <p key={note} role="status" className="text-sm">
          {note}
        </p>
      ))}
      {items.length === 0 ? (
        <p className="text-muted-foreground">
          Keine offenen Vorschläge.
          {open.data.total === 0 && " Sie entstehen im nächsten Lauf."}
        </p>
      ) : (
        <ul className="flex flex-col">
          {items.map((proposal) => (
            <ProposalRow
              key={proposal.id}
              proposal={proposal}
              topics={topics.data ?? []}
              onDecided={(message) => {
                setNotes((current) => [message, ...current])
                setVersion((current) => current + 1)
              }}
            />
          ))}
        </ul>
      )}
      {decided.length > 0 && (
        <details>
          <summary className="cursor-pointer py-1 text-sm font-medium underline-offset-2 hover:underline">
            Entschieden ({done.data?.total ?? decided.length})
          </summary>
          <ul className="flex flex-col gap-1 pt-2 text-xs text-muted-foreground">
            {decided.map((proposal) => (
              <li key={proposal.id}>
                <span className="font-semibold text-foreground">
                  {proposal.decision ? DECISION_TEXT[proposal.decision] : ""}
                </span>
                : {proposal.name_de}
                {proposal.decided_by ? ` · von ${proposal.decided_by}` : ""}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
