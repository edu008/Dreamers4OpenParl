import { Fragment } from "react"
import { Link, useParams } from "react-router"

import { AffairTable } from "@/components/affair-table"
import { PageRow } from "@/components/page-tree"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import type { PageTree, WikiPage } from "@/lib/api"
import { sampleRowsForPage } from "@/lib/sample-affairs"
import {
  ancestorsOf,
  childrenOf,
  KIND_LABEL,
  linkedQuerschnitt,
  pageHref,
} from "@/lib/tree"

/** Tag-, Kapitel-, Bereichs- oder Querschnittsseite (PRD 7.9). Inhalt folgt in M3. */
export function TagPage() {
  const { tagId = "" } = useParams()
  const tree = useApi<PageTree>("/v1/pages")

  if (tree.loading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-4 w-64" />
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }
  if (tree.error || !tree.data) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Seitenbaum nicht geladen</AlertTitle>
        <AlertDescription>{tree.error}</AlertDescription>
      </Alert>
    )
  }

  const pages = tree.data.pages
  const page = pages.find((candidate) => candidate.page_id === tagId)
  if (!page) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Seite nicht gefunden</AlertTitle>
        <AlertDescription>
          Zu „{tagId}“ gibt es keine aktive Seite.{" "}
          <Link to="/">Zum Seitenbaum</Link>
        </AlertDescription>
      </Alert>
    )
  }

  const kids = childrenOf(pages, page.page_id)
  const linked =
    page.kind === "querschnitt"
      ? pages.filter((other) => page.linked_from.includes(other.page_id))
      : linkedQuerschnitt(pages, page.page_id)

  const sampleRows = sampleRowsForPage(page.page_id)

  return (
    <>
      <Breadcrumb>
        <BreadcrumbList>
          {ancestorsOf(pages, page.page_id).map((ancestor) => (
            <Fragment key={ancestor.page_id}>
              <BreadcrumbItem>
                <BreadcrumbLink render={<Link to={pageHref(ancestor)} />}>
                  {ancestor.title}
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
            </Fragment>
          ))}
          <BreadcrumbItem>
            <BreadcrumbPage>{page.title}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">{KIND_LABEL[page.kind]}</Badge>
          <span className="font-mono text-xs text-muted-foreground">
            {page.page_id}
          </span>
        </div>
        <h1 className="font-heading text-2xl font-medium">{page.title}</h1>
        <p className="font-mono text-xs text-muted-foreground">
          wiki/{page.path}
        </p>
      </div>
      {sampleRows.length > 0 && (
        <section aria-labelledby="affairs-heading" className="flex flex-col gap-2">
          <h2 id="affairs-heading" className="font-heading text-lg font-medium">
            Geschäfte
          </h2>
          <p className="text-xs text-muted-foreground">
            Beispieldaten, nicht aus OpenParlData. Die echte Liste kommt aus der API, sobald
            Labels vorliegen.
          </p>
          <AffairTable rows={sampleRows} />
        </section>
      )}
      <Alert>
        <AlertTitle>Inhalt folgt in Meilenstein M3</AlertTitle>
        <AlertDescription>
          Beschreibung, Kurzzusammenfassung, Zusammenfassung der letzten zwölf
          Monate mit Belegen, Kennzahlen und Geschäftsliste entstehen aus der
          Datenbank (PRD 7.9, F23 bis F25).
        </AlertDescription>
      </Alert>
      <PageList
        title="Unterseiten"
        description="Diese Seite fasst ihre Unterseiten zusammen."
        pages={kids}
      />
      <PageList
        title={
          page.kind === "querschnitt" ? "Verlinkt aus" : "Querschnittsthemen"
        }
        description={
          page.kind === "querschnitt"
            ? "Kapitel und Themen, denen dieses Ad-hoc-Thema zugeordnet ist."
            : "Ad-hoc-Themen, die hier verlinkt, aber nicht mitgezählt werden."
        }
        pages={linked}
      />
    </>
  )
}

function PageList({
  title,
  description,
  pages,
}: {
  title: string
  description: string
  pages: WikiPage[]
}) {
  if (pages.length === 0) {
    return null
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-2">
          {pages.map((other) => (
            <li key={other.page_id}>
              <PageRow page={other} />
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
