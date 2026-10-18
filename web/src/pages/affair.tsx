import { Link, useParams } from "react-router"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { EvidenceText } from "@/components/evidence-text"
import { MarginNotes, type MarginLabel } from "@/components/margin-notes"
import { Button } from "@/components/ui/button"
import { useReview } from "@/hooks/use-review"
import { buildQueue, nextOpenRow } from "@/lib/review-queue"
import { evidenceFound, reviewReasons } from "@/lib/label-state"
import { findSampleAffair } from "@/lib/sample-affairs"

const LANGUAGE_NAME = {
  de: "Deutsch",
  fr: "Französisch",
  it: "Italienisch",
} as const

function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-")
  return `${day}.${month}.${year}`
}

// "public": rein lesend, mit Link in die Prüfansicht. "review": Prüfansicht unter /review, dort
// stehen nach der Anmeldung die Knöpfe zum Bestätigen und Verwerfen (Council 18.10.2026).
export function AffairPage({ mode }: { mode: "public" | "review" }) {
  const { affairId = "" } = useParams()
  const affair = findSampleAffair(affairId)
  const review = useReview()
  const next = nextOpenRow(buildQueue(review.decisions), affairId)
  const base = mode === "review" ? "/review/geschaefte" : "/geschaefte"

  if (!affair) {
    return (
      <Alert>
        <AlertTitle>Geschäft nicht gefunden</AlertTitle>
        <AlertDescription>
          Zu {affairId} gibt es noch keine Daten. Bis die API Labels liefert,
          zeigt die Seite nur Beispielgeschäfte.{" "}
          <Link to={`${base}/70435`}>Beispiel öffnen</Link>
        </AlertDescription>
      </Alert>
    )
  }

  const labels: MarginLabel[] = affair.labels.map((label) => ({
    ...label,
    evidenceFound: evidenceFound(affair, label),
    needsReview: reviewReasons(affair, label).length > 0,
  }))
  const spans = labels
    .filter((label) => label.evidence !== null && label.evidenceFound)
    .map((label) => ({ key: label.tagId, text: label.evidence as string }))

  return (
    <article className="flex flex-col gap-4">
      <nav aria-label="Pfad" className="text-xs text-muted-foreground">
        {mode === "review" ? (
          <Link to="/review" className="underline underline-offset-2">
            Review
          </Link>
        ) : (
          <Link to="/" className="underline underline-offset-2">
            Wiki
          </Link>
        )}{" "}
        / Geschäft {affair.number}
      </nav>
      <p className="text-xs text-muted-foreground">
        Beispieldaten, nicht aus OpenParlData. Echte Labels folgen mit der
        Klassifikation.
      </p>
      {mode === "review" && (
        <nav
          aria-label="Review"
          className="flex flex-wrap items-center gap-3 text-xs"
        >
          {next ? (
            <Button
              size="sm"
              variant="outline"
              nativeButton={false}
              render={<Link to={`/review/geschaefte/${next.affair.id}`} />}
            >
              Nächstes offenes Label
            </Button>
          ) : (
            <span className="text-muted-foreground">
              Keine weiteren offenen Labels.
            </span>
          )}
          <Link
            to="/review"
            className="text-muted-foreground underline underline-offset-2"
          >
            Zur Warteschlange
          </Link>
          {!review.active && (
            <span className="text-muted-foreground">
              Zum Entscheiden zuerst{" "}
              <Link to="/review" className="underline underline-offset-2">
                auf der Seite Review anmelden
              </Link>
              .
            </span>
          )}
        </nav>
      )}
      <div className="grid gap-0 border-t border-foreground lg:grid-cols-[minmax(0,1fr)_14rem]">
        <div className="flex flex-col gap-4 py-5 lg:pr-8">
          <p className="tabular text-xs text-muted-foreground">
            {affair.number} · {affair.type} · {affair.body} ·{" "}
            {formatDate(affair.date)}
          </p>
          <h1
            lang={affair.language}
            className="font-heading text-2xl leading-tight font-semibold text-balance"
          >
            {affair.title}
          </h1>
          <div className="flex max-w-[68ch] flex-col gap-4">
            {affair.paragraphs.map((paragraph) => (
              <EvidenceText
                key={paragraph}
                paragraph={paragraph}
                spans={spans}
                lang={affair.language}
              />
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Originalsprache: {LANGUAGE_NAME[affair.language]}
            {affair.sourceUrl && (
              <>
                {" "}
                ·{" "}
                <a
                  href={affair.sourceUrl}
                  className="underline underline-offset-2"
                >
                  Quelle
                </a>
              </>
            )}
          </p>
        </div>
        <MarginNotes
          mode={mode}
          affairId={affair.id}
          labels={labels}
          versions={{
            model: affair.model,
            prompt: affair.promptVersion,
            registry: affair.registryVersion,
          }}
        />
      </div>
    </article>
  )
}
