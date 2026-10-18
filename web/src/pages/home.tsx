import { Link } from "react-router"

import { PageTree } from "@/components/page-tree"
import { SearchForm } from "@/components/search-form"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import type { PageTree as PageTreeData, TopicOut } from "@/lib/api"
import { HEART_ID } from "@/lib/tree"

export function HomePage() {
  const tree = useApi<PageTreeData>("/v1/pages")
  const topics = useApi<TopicOut[]>("/v1/topics")
  const counts = new Map(
    (topics.data ?? []).map((topic) => [topic.tag_id, topic.n_affairs])
  )
  const frequent = [...(topics.data ?? [])]
    .filter((topic) => topic.n_affairs > 0)
    .sort((a, b) => b.n_affairs - a.n_affairs)
    .slice(0, 5)
  const heart = tree.data?.pages.find((page) => page.page_id === HEART_ID)
  return (
    <>
      <div className="flex flex-col gap-3">
        <h1 className="font-heading text-3xl leading-tight font-semibold text-balance">
          Geschäfte der Schweizer Parlamente nach Thema finden
        </h1>
        <p className="max-w-[68ch] text-muted-foreground">
          Frage in eigenen Worten. Jedes Ergebnis zeigt die Textstelle, die das
          Thema begründet.
        </p>
        <SearchForm />
        {frequent.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Häufige Themen:{" "}
            {frequent.map((topic, index) => (
              <span key={topic.tag_id}>
                {index > 0 && " · "}
                <Link
                  to={`/tags/${topic.tag_id}`}
                  className="inline-block py-2 underline underline-offset-2"
                >
                  {topic.name_de}
                </Link>
              </span>
            ))}
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          Anwendungsfall Digitale Verwaltung Schweiz:{" "}
          <Link
            to="/tags/adhoc:digitalisierung-breit"
            className="inline-block py-2 underline underline-offset-2"
          >
            Digitalisierung im ganzen Bestand
          </Link>{" "}
          mit Auswertung und CSV-Export.
        </p>
      </div>
      <section
        aria-labelledby="topics-heading"
        className="flex flex-col gap-3 pt-2"
      >
        <h2 id="topics-heading" className="font-heading text-lg font-medium">
          Nach Thema stöbern
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
        {tree.data && heart && (
          <PageTree
            pages={tree.data.pages}
            root={heart}
            counts={topics.data ? counts : undefined}
          />
        )}
      </section>
    </>
  )
}
