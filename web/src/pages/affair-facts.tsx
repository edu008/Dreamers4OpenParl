import type { ReactNode } from "react"
import { Link, useLocation, useParams } from "react-router"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import { usePageTitle } from "@/hooks/use-page-title"
import type { AffairTopics } from "@/lib/api"
import { LEVEL_LABEL } from "@/lib/export"
import { paragraphsOf } from "@/pages/affair"

const LANGUAGE_NAME: Record<string, string> = {
  de: "Deutsch",
  fr: "Französisch",
  it: "Italienisch",
  rm: "Rätoromanisch",
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return ""
  const [year, month, day] = iso.split("-")
  return `${day}.${month}.${year}`
}

/** Abschnitt im Raster: Titel in der linken Spalte, Inhalt rechts. */
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid gap-x-8 gap-y-3 border-t-2 border-foreground pt-4 sm:grid-cols-[12rem_minmax(0,1fr)]">
      <h2 className="text-lg font-bold">{title}</h2>
      <div className="min-w-0">{children}</div>
    </section>
  )
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl>
      {rows.map(([term, value]) => (
        <div
          key={term}
          className="grid gap-x-6 gap-y-1 border-t border-border py-3 first:border-t-0 first:pt-0 sm:grid-cols-[10rem_minmax(0,1fr)]"
        >
          <dt className="text-sm font-bold">{term}</dt>
          <dd className="min-w-0 break-words">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

// Öffentliche Geschäftsseite: die Fakten wie bei OpenParlData und die Themen, ohne Konfidenz,
// Modell oder Prüfstand. Die Prüfansicht mit allen Angaben liegt unter /admin/review.
export function AffairFactsPage() {
  const { affairId = "" } = useParams()
  const fromSearch = (useLocation().state as { search?: string } | null)?.search
  const back = { pathname: "/", search: fromSearch ?? "" }
  const found = useApi<AffairTopics>(
    `/v1/affairs/${encodeURIComponent(affairId)}/topics`
  )
  usePageTitle(found.data?.title ?? "Geschäft")

  if (found.loading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (found.error || !found.data) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Geschäft nicht geladen</AlertTitle>
        <AlertDescription>
          {found.error} <Link to={back}>Zur Suche</Link>
        </AlertDescription>
      </Alert>
    )
  }

  const affair = found.data
  const title = affair.title ?? `Geschäft ${affair.affair_id}`
  const type = affair.type_de ?? affair.type
  const language = affair.language ?? "de"
  const paragraphs = paragraphsOf(affair.text)
  const topics = affair.labels.filter((label) => label.status === "active")
  const level = affair.body_level
    ? (LEVEL_LABEL[affair.body_level] ?? affair.body_level)
    : null

  const details: [string, ReactNode][] = [
    ["ID", <span className="tabular">{affair.affair_id}</span>],
  ]
  if (affair.external_id) details.push(["Externe ID", affair.external_id])
  if (affair.number) details.push(["Nummer", affair.number])
  details.push(["Titel", <span lang={language}>{title}</span>])
  if (affair.title_long && affair.title_long !== affair.title) {
    details.push([
      "Langer Titel",
      <span lang={language}>{affair.title_long}</span>,
    ])
  }
  if (type) {
    const original =
      affair.type_name && affair.type_name !== type
        ? ` (${affair.type_name})`
        : ""
    details.push(["Typ", `${type}${original}`])
  }
  if (affair.state) details.push(["Stand", affair.state])
  if (affair.begin_date) details.push(["Beginn", formatDate(affair.begin_date)])
  if (affair.end_date) details.push(["Ende", formatDate(affair.end_date)])
  if (affair.url_external) {
    details.push([
      "URL",
      <a
        href={affair.url_external}
        className="break-all underline underline-offset-4 hover:text-primary"
      >
        {affair.url_external}
      </a>,
    ])
  }

  const area: [string, ReactNode][] = [
    ["Parlament", affair.body_name ?? affair.body_key],
  ]
  if (level) area.push(["Ebene", level])
  area.push(["Kürzel", affair.body_key])

  const meta = [
    "Geschäft",
    affair.number && `Nr. ${affair.number}`,
    formatDate(affair.begin_date),
    type,
  ]

  return (
    <article className="flex flex-col gap-10">
      <Link
        to={back}
        className="self-start text-sm font-bold underline-offset-4 hover:text-primary hover:underline"
      >
        ← Geschäfte
      </Link>
      <header className="flex flex-col gap-4">
        <p className="tabular text-sm text-muted-foreground">
          {meta.filter(Boolean).join(" | ")}
        </p>
        <h1
          lang={language}
          className="font-heading text-[clamp(1.75rem,4vw,3rem)] leading-[1.05] font-bold tracking-[-0.02em] text-balance"
        >
          {title}
        </h1>
        {topics.length > 0 && (
          <ul aria-label="Themen" className="flex flex-wrap gap-2 pt-2">
            {topics.map((topic) => (
              <li key={topic.id}>
                <Link
                  to={`/?thema=${encodeURIComponent(topic.tag_id)}`}
                  className="inline-flex min-h-9 items-center bg-foreground px-3 text-sm font-bold text-background transition-colors hover:bg-primary"
                >
                  {topic.name_de}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </header>

      <Section title="Geschäft">
        <Facts rows={details} />
      </Section>

      {paragraphs.length > 0 && (
        <Section title="Text">
          <div lang={language} className="flex max-w-[68ch] flex-col gap-4">
            {paragraphs.map((paragraph) => (
              <p
                key={paragraph}
                className="font-reading text-[17px] leading-relaxed"
              >
                {paragraph}
              </p>
            ))}
            <p className="text-sm text-muted-foreground">
              Originalsprache: {LANGUAGE_NAME[language] ?? language}
            </p>
          </div>
        </Section>
      )}

      <Section title="Gebiet">
        <Facts rows={area} />
      </Section>
    </article>
  )
}
