import { AffairTable } from "@/components/affair-table"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import type { TopicAffairs as TopicAffairsData, WikiPage } from "@/lib/api"

const LIMIT = 100

// Geschäfte eines Themas aus der Sidecar-API. Bereiche, Kapitel und die Wurzel tragen selbst
// keine Labels und zeigen deshalb keinen Abschnitt.
export function TopicAffairs({ page }: { page: WikiPage }) {
  if (page.kind !== "tag" && page.kind !== "querschnitt") return null
  return <TopicAffairsList tagId={page.page_id} />
}

function TopicAffairsList({ tagId }: { tagId: string }) {
  const found = useApi<TopicAffairsData>(
    `/v1/topics/${encodeURIComponent(tagId)}/affairs?limit=${LIMIT}`
  )
  return (
    <section aria-labelledby="affairs-heading" className="flex flex-col gap-2">
      <h2 id="affairs-heading" className="font-heading text-lg font-medium">
        Geschäfte{found.data ? ` (${found.data.total})` : ""}
      </h2>
      {found.loading && <Skeleton className="h-24 w-full" />}
      {found.error && (
        <p className="text-sm text-destructive">
          Geschäfte nicht geladen: {found.error}
        </p>
      )}
      {found.data && found.data.total === 0 && (
        <p className="text-muted-foreground">
          Noch keine Geschäfte mit diesem Thema.
        </p>
      )}
      {found.data && found.data.total > 0 && (
        <>
          {found.data.total > found.data.items.length && (
            <p className="text-xs text-muted-foreground">
              Die {found.data.items.length} Geschäfte mit der höchsten Konfidenz
              von {found.data.total}.
            </p>
          )}
          <AffairTable rows={found.data.items} />
        </>
      )}
    </section>
  )
}
