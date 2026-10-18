import { Link, useParams } from "react-router"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { EvidenceText, isEvidenceFound } from "@/components/evidence-text"
import { MarginNotes, type MarginLabel } from "@/components/margin-notes"
import { findSampleAffair } from "@/lib/sample-affairs"

// Schwelle aus der Klassifikation (CONFIDENCE_THRESHOLD, Startwert 0.6). Wird später aus der API gelesen.
const REVIEW_BELOW = 0.6

const LANGUAGE_NAME = { de: "Deutsch", fr: "Französisch", it: "Italienisch" } as const

function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-")
  return `${day}.${month}.${year}`
}

export function AffairPage() {
  const { affairId = "" } = useParams()
  const affair = findSampleAffair(affairId)

  if (!affair) {
    return (
      <Alert>
        <AlertTitle>Geschäft nicht gefunden</AlertTitle>
        <AlertDescription>
          Zu {affairId} gibt es noch keine Daten. Bis die API Labels liefert, zeigt die Seite nur
          Beispielgeschäfte. <Link to="/geschaefte/70435">Beispiel öffnen</Link>
        </AlertDescription>
      </Alert>
    )
  }

  const labels: MarginLabel[] = affair.labels.map((label) => ({
    ...label,
    evidenceFound:
      label.evidence !== null && isEvidenceFound(affair.paragraphs, label.evidence),
    needsReview:
      label.confidence < REVIEW_BELOW ||
      label.evidence === null ||
      !isEvidenceFound(affair.paragraphs, label.evidence),
  }))
  const spans = labels
    .filter((label) => label.evidence !== null && label.evidenceFound)
    .map((label) => ({ key: label.tagId, text: label.evidence as string }))

  return (
    <article className="flex flex-col gap-4">
      <nav aria-label="Pfad" className="text-xs text-muted-foreground">
        <Link to="/" className="underline underline-offset-2">
          Wiki
        </Link>{" "}
        / Geschäft {affair.number}
      </nav>
      <p className="text-xs text-muted-foreground">
        Beispieldaten, nicht aus OpenParlData. Echte Labels folgen mit der Klassifikation.
      </p>
      <div className="grid gap-0 border-t border-foreground lg:grid-cols-[minmax(0,1fr)_14rem]">
        <div className="flex flex-col gap-4 py-5 lg:pr-8">
          <p className="tabular text-xs text-muted-foreground">
            {affair.number} · {affair.type} · {affair.body} · {formatDate(affair.date)}
          </p>
          <h1
            lang={affair.language}
            className="font-reading text-2xl leading-tight font-semibold text-balance"
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
            Originalsprache: {LANGUAGE_NAME[affair.language]} ·{" "}
            <a href={affair.sourceUrl} className="underline underline-offset-2">
              Quelle
            </a>
          </p>
        </div>
        <MarginNotes
          labels={labels}
          versions={`${affair.model} · Prompt ${affair.promptVersion} · Registry ${affair.registryVersion}`}
        />
      </div>
    </article>
  )
}
