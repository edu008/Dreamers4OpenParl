import { Fragment } from "react"
import { Link } from "react-router"

import type { WikiPage } from "@/lib/api"
import { childrenOf, KIND_LABEL, linkedQuerschnitt, pageHref } from "@/lib/tree"

/** Seitenbaum ab einer Wurzel: Bereiche, Kapitel und Themen zum Aufklappen. Die Wurzel selbst
 * (Heart) bleibt unsichtbar, die Übersicht beginnt bei den Bereichen. */
export function PageTree({
  pages,
  root,
}: {
  pages: WikiPage[]
  root: WikiPage
}) {
  return (
    <ul className="flex flex-col gap-2">
      {childrenOf(pages, root.page_id).map((child) => (
        <TreeNode key={child.page_id} page={child} pages={pages} />
      ))}
    </ul>
  )
}

function TreeNode({ page, pages }: { page: WikiPage; pages: WikiPage[] }) {
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
        <PageRow page={page} />
        {links}
      </li>
    )
  }
  return (
    <li>
      <details className="group">
        <summary className="flex cursor-pointer list-none items-baseline gap-2 marker:hidden">
          <span aria-hidden="true" className="w-4 text-muted-foreground group-open:rotate-90">
            ›
          </span>
          <PageRow page={page} />
        </summary>
        {links}
        <ul className="mt-2 ml-2 flex flex-col gap-2 border-l border-border pl-4">
          {kids.map((child) => (
            <TreeNode key={child.page_id} page={child} pages={pages} />
          ))}
        </ul>
      </details>
    </li>
  )
}

export function PageRow({ page }: { page: WikiPage }) {
  return (
    <div className="flex flex-wrap items-baseline gap-2">
      <Link
        to={pageHref(page)}
        className="font-medium underline-offset-4 hover:underline"
      >
        {page.title}
      </Link>
      {(page.kind === "querschnitt" || page.kind === "bereich") && (
        <span className="text-xs text-muted-foreground">
          {KIND_LABEL[page.kind]}
        </span>
      )}
    </div>
  )
}
