import { Fragment } from "react"
import { Link } from "react-router"

import type { WikiPage } from "@/lib/api"
import { childrenOf, KIND_LABEL, linkedQuerschnitt, pageHref } from "@/lib/tree"

/** Seitenbaum ab einer Wurzel: Bereiche, Kapitel und Themen zum Aufklappen. Die Wurzel selbst
 * (Heart) bleibt unsichtbar, die Übersicht beginnt bei den Bereichen. */
export function PageTree({
  pages,
  root,
  counts,
}: {
  pages: WikiPage[]
  root: WikiPage
  counts?: Map<string, number>
}) {
  return (
    <ul className="flex flex-col gap-2">
      {childrenOf(pages, root.page_id).map((child) => (
        <TreeNode
          key={child.page_id}
          page={child}
          pages={pages}
          counts={counts}
        />
      ))}
    </ul>
  )
}

function TreeNode({
  page,
  pages,
  counts,
}: {
  page: WikiPage
  pages: WikiPage[]
  counts?: Map<string, number>
}) {
  const kids = childrenOf(pages, page.page_id)
  const linked = linkedQuerschnitt(pages, page.page_id)
  const links =
    linked.length > 0 ? (
      <p className="pl-6 text-xs text-muted-foreground">
        Verlinkt:{" "}
        {linked.map((other, index) => (
          <Fragment key={other.page_id}>
            {index > 0 && ", "}
            <Link to={pageHref(other)} className="underline underline-offset-4">
              {other.title}
            </Link>
          </Fragment>
        ))}
      </p>
    ) : null
  if (kids.length === 0) {
    return (
      <li className="flex flex-col gap-1 pl-4">
        <PageRow
          page={page}
          count={counts ? totalFor(pages, page, counts) : undefined}
        />
        {links}
      </li>
    )
  }
  return (
    <li>
      <details className="group">
        <summary className="flex cursor-pointer list-none items-baseline gap-2 marker:hidden">
          <span
            aria-hidden="true"
            className="w-4 text-muted-foreground group-open:rotate-90"
          >
            ›
          </span>
          <PageRow
            page={page}
            count={counts ? totalFor(pages, page, counts) : undefined}
          />
        </summary>
        {links}
        <ul className="mt-2 ml-2 flex flex-col gap-2 border-l border-border pl-4">
          {kids.map((child) => (
            <TreeNode
              key={child.page_id}
              page={child}
              pages={pages}
              counts={counts}
            />
          ))}
        </ul>
      </details>
    </li>
  )
}

/** Geschäfte einer Seite samt aller Unterseiten (die API zählt nur je Thema). */
function totalFor(
  pages: WikiPage[],
  page: WikiPage,
  counts: Map<string, number>
): number {
  const own = counts.get(page.page_id) ?? 0
  return childrenOf(pages, page.page_id).reduce(
    (sum, child) => sum + totalFor(pages, child, counts),
    own
  )
}

export function PageRow({ page, count }: { page: WikiPage; count?: number }) {
  return (
    <div className="flex flex-wrap items-baseline gap-2">
      <Link
        to={pageHref(page)}
        className="font-medium underline-offset-4 hover:underline"
      >
        {page.title}
      </Link>
      {count !== undefined && count > 0 && (
        <span className="tabular text-xs text-muted-foreground">{count}</span>
      )}
      {(page.kind === "querschnitt" || page.kind === "bereich") && (
        <span className="text-xs text-muted-foreground">
          {KIND_LABEL[page.kind]}
        </span>
      )}
    </div>
  )
}
