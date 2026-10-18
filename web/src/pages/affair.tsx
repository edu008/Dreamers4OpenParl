import { Link, useParams } from "react-router"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { EvidenceText, isEvidenceFound } from "@/components/evidence-text"
import { MarginNotes, type MarginLabel } from "@/components/margin-notes"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import { useReview } from "@/hooks/use-review"
import { useReviewQueue } from "@/hooks/use-review-queue"
import type { AffairTopics } from "@/lib/api"
import { reviewReasons } from "@/lib/label-state"
import { buildQueue, nextOpenRow } from "@/lib/review-queue"

const LANGUAGE_NAME: Record<string, string> = {
  de: "Deutsch",
  fr: "Französisch",
  it: "Italienisch",
  rm: "Rätoromanisch",
}

function formatDate(iso: string | null): string {
  if (!iso) return ""
  const [year, month, day] = iso.split("-")
  return `${day}.${month}.${year}`
}

/** Der Klassifikationstext beginnt mit dem Titel, danach folgen die Absätze (durch \n getrennt). */
function paragraphsOf(text: string | null): string[] {
  const lines = (text ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
  return lines.slice(1)
}

// "public": rein lesend, mit Link in die Prüfansicht. "review": Prüfansicht unter /review, dort
// stehen nach der Anmeldung die Knöpfe zum Bestätigen und Verwerfen (Council 18.10.2026).
export function AffairPage({ mode }: { mode: "public" | "review" }) {
  const { affairId = "" } = useParams()
  const found = useApi<AffairTopics>(
    `/v1/affairs/${encodeURIComponent(affairId)}/topics`
  )
  const review = useReview()
  const queue = useReviewQueue()
  const next = nextOpenRow(
    buildQueue(queue.candidates, review.decisions),
    affairId
  )

  if (found.loading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-4 w-64" />
        <Skeleton className="h-8 w-96" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }
  if (found.error || !found.data) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Geschäft nicht geladen</AlertTitle>
        <AlertDescription>
          {found.error} <Link to="/">Zur Themenübersicht</Link>
        </AlertDescription>
      </Alert>
    )
  }

  const affair = found.data
  const language = affair.language ?? "de"
  const paragraphs = paragraphsOf(affair.text)
  const active = affair.labels.filter((label) => label.status === "active")
  const labels: MarginLabel[] = active.map((label) => ({
    tagId: label.tag_id,
    name: label.name_de,
    confidence: label.confidence,
    evidence: label.evidence,
    stage: label.stage,
    evidenceVerified: label.evidence_verified,
    evidenceMarked:
      label.evidence !== null && isEvidenceFound(paragraphs, label.evidence),
    needsReview:
      reviewReasons({
        confidence: label.confidence,
        evidence: label.evidence,
        evidenceVerified: label.evidence_verified,
      }).length > 0,
  }))
  const spans = labels
    .filter((label) => label.evidenceMarked)
    .map((label) => ({ key: label.tagId, text: label.evidence as string }))
  const first = active[0] ?? affair.labels[0]
  const versions = first
    ? {
        model: first.model_version,
        prompt: first.prompt_version,
        registry: first.registry_version,
      }
    : null

  return (
    <article className="flex flex-col gap-4">
      <nav aria-label="Pfad" className="text-xs text-muted-foreground">
        {mode === "review" ? (
          <Link to="/review" className="underline underline-offset-2">
            Review
          </Link>
        ) : (
          <Link to="/" className="underline underline-offset-2">
            Themen
          </Link>
        )}{" "}
        / Geschäft {affair.number ?? affair.affair_id}
      </nav>
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
              render={<Link to={`/review/geschaefte/${next.affairId}`} />}
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
              Zum Entscheiden oben rechts die Ansicht «Reviewer» wählen.
            </span>
          )}
        </nav>
      )}
      <div className="grid gap-0 border-t border-foreground lg:grid-cols-[minmax(0,1fr)_14rem]">
        <div className="flex flex-col gap-4 py-5 lg:pr-8">
          <p className="tabular text-xs text-muted-foreground">
            {[
              affair.number,
              affair.type,
              affair.body_name ?? affair.body_key,
              formatDate(affair.begin_date),
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <h1
            lang={language}
            className="font-heading text-2xl leading-tight font-semibold text-balance"
          >
            {affair.title}
          </h1>
          <div className="flex max-w-[68ch] flex-col gap-4">
            {paragraphs.map((paragraph) => (
              <EvidenceText
                key={paragraph}
                paragraph={paragraph}
                spans={spans}
                lang={language}
              />
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Originalsprache: {LANGUAGE_NAME[language] ?? language}
            {affair.url_external && (
              <>
                {" "}
                ·{" "}
                <a
                  href={affair.url_external}
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
          affairId={String(affair.affair_id)}
          labels={labels}
          versions={versions}
        />
      </div>
    </article>
  )
}
