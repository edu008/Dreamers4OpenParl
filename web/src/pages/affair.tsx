import { useState } from "react"
import { Link, useParams } from "react-router"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { EvidenceText, isEvidenceFound } from "@/components/evidence-text"
import { MarginNotes, type MarginLabel } from "@/components/margin-notes"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import { usePageTitle } from "@/hooks/use-page-title"
import { useReview } from "@/hooks/use-review"
import { useReviewQueue } from "@/hooks/use-review-queue"
import type { AffairTopics } from "@/lib/api"
import { reviewReasons } from "@/lib/label-state"
import { nextOpen } from "@/lib/review-queue"

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
  usePageTitle(
    found.data
      ? `${found.data.number ?? found.data.affair_id} ${found.data.title}`
      : "Geschäft"
  )
  const review = useReview()
  const queue = useReviewQueue()
  const next = nextOpen(queue.open, affairId)
  // Nach einem Entscheid liefert POST /v1/reviews das Geschäft mit den neuen Labels.
  const [saved, setSaved] = useState<AffairTopics | null>(null)
  const [pendingId, setPendingId] = useState<number | null>(null)
  const [saveError, setSaveError] = useState<string>()

  async function onDecide(
    label: MarginLabel,
    action: "confirm" | "reject" | "undo"
  ) {
    setPendingId(label.id)
    setSaveError(undefined)
    try {
      setSaved(await review.decide(affairId, label.tagId, action))
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : String(error))
    } finally {
      setPendingId(null)
    }
  }

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

  const affair = saved?.affair_id === found.data.affair_id ? saved : found.data
  const language = affair.language ?? "de"
  const paragraphs = paragraphsOf(affair.text)
  const active = affair.labels.filter((label) => label.status === "active")
  // Verworfene Labels bleiben mit Entscheid sichtbar; Ersetztes (superseded) gehört zum Verlauf.
  const shown = affair.labels.filter(
    (label) =>
      label.status === "active" ||
      (label.status === "rejected" && label.review_status !== null)
  )
  const labels: MarginLabel[] = shown.map((label) => ({
    id: label.id,
    status: label.status,
    reviewStatus: label.review_status,
    reviewedBy: label.reviewed_by,
    tagId: label.tag_id,
    name: label.name_de,
    confidence: label.confidence,
    evidence: label.evidence,
    stage: label.stage,
    evidenceVerified: label.evidence_verified,
    evidenceMarked:
      label.evidence !== null && isEvidenceFound(paragraphs, label.evidence),
    needsReview:
      label.status === "active" &&
      label.review_status === null &&
      reviewReasons(
        {
          confidence: label.confidence,
          evidence: label.evidence,
          evidenceVerified: label.evidence_verified,
        },
        queue.threshold
      ).length > 0,
  }))
  const spans = labels
    .filter((label) => label.status === "active" && label.evidenceMarked)
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
              Zum Entscheiden oben rechts die Ansicht «Admin» wählen.
            </span>
          )}
        </nav>
      )}
      <div className="grid gap-0 border-t border-foreground lg:grid-cols-[minmax(0,1fr)_14rem]">
        <div className="flex flex-col gap-4 py-5 lg:pr-8">
          <p className="tabular text-xs text-muted-foreground">
            {[
              affair.number,
              affair.type_de ?? affair.type,
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
        <div className="lg:border-l lg:border-border">
          <div className="lg:sticky lg:top-6">
            <MarginNotes
              mode={mode}
              affairId={String(affair.affair_id)}
              labels={labels}
              versions={versions}
              pendingId={pendingId}
              error={saveError}
              onDecide={onDecide}
            />
          </div>
        </div>
      </div>
    </article>
  )
}
