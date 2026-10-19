import { Link } from "react-router"

import { useApi } from "@/hooks/use-api"

interface Related {
  tag_id: string
  name_de: string
  /** Geschäfte mit beiden Themen (aktive Labels). */
  shared: number
  /** In der Registry als verwandt eingetragen. */
  in_registry: boolean
}

// Verwandte Themen: zuerst die in der Registry eingetragenen, dann die mit den meisten gemeinsamen
// Geschäften. Beides getrennt zu zeigen verhindert, dass Zufall wie Redaktion aussieht.
export function RelatedTopics({ tagId }: { tagId: string }) {
  const related = useApi<Related[]>(
    `/v1/topics/${encodeURIComponent(tagId)}/related?limit=10`
  )
  if (related.loading || related.error || !related.data) return null
  if (related.data.length === 0) return null
  const curated = related.data.filter((topic) => topic.in_registry)
  const common = related.data.filter((topic) => !topic.in_registry)

  const list = (topics: Related[]) => (
    <ul className="flex flex-col gap-1 text-sm">
      {topics.map((topic) => (
        <li key={topic.tag_id}>
          <Link
            to={`/admin/themen/${topic.tag_id}`}
            className="underline underline-offset-2"
          >
            {topic.name_de}
          </Link>{" "}
          <span className="tabular text-xs text-muted-foreground">
            {topic.shared === 0
              ? "noch keine gemeinsamen Geschäfte"
              : `${topic.shared} gemeinsame${topic.shared === 1 ? "s" : ""} Geschäft${topic.shared === 1 ? "" : "e"}`}
          </span>
        </li>
      ))}
    </ul>
  )

  return (
    <section
      aria-labelledby="related-heading"
      className="flex flex-col gap-2"
    >
      <h2 id="related-heading" className="font-heading text-lg font-medium">
        Verwandte Themen
      </h2>
      {curated.length > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="text-xs font-semibold">In der Registry verknüpft</h3>
          {list(curated)}
        </div>
      )}
      {common.length > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="text-xs font-semibold">Oft zusammen mit</h3>
          {list(common)}
        </div>
      )}
    </section>
  )
}
