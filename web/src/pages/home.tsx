import { PageTree } from "@/components/page-tree"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import type { PageTree as PageTreeData } from "@/lib/api"
import { HEART_ID } from "@/lib/tree"

export function HomePage() {
  const tree = useApi<PageTreeData>("/v1/pages")
  const heart = tree.data?.pages.find((page) => page.page_id === HEART_ID)
  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="font-reading text-2xl leading-tight font-semibold text-balance">
          Themen der Schweizer Parlamente
        </h1>
        <p className="max-w-[68ch] text-muted-foreground">
          Geschäfte aus Bund, Kantonen und Gemeinden, nach Themen geordnet und mit der Textstelle
          belegt, die das Thema begründet. Wähle einen Bereich, ein Kapitel und dann ein Thema.
        </p>
      </div>
      <section aria-labelledby="topics-heading" className="flex flex-col gap-3 border-t border-foreground pt-4">
        <h2 id="topics-heading" className="font-heading text-lg font-medium">
          Themenübersicht
        </h2>
        {tree.loading && (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-5 w-64" />
            <Skeleton className="h-5 w-56" />
          </div>
        )}
        {tree.error && (
          <Alert variant="destructive">
            <AlertTitle>Themen nicht geladen</AlertTitle>
            <AlertDescription>{tree.error}</AlertDescription>
          </Alert>
        )}
        {tree.data && heart && <PageTree pages={tree.data.pages} root={heart} />}
      </section>
    </>
  )
}
