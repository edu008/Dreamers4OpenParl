import { Fragment } from "react"
import { Link } from "react-router"

import { Badge } from "@/components/ui/badge"
import type { WikiPage } from "@/lib/api"
import { childrenOf, KIND_LABEL, linkedQuerschnitt, pageHref } from "@/lib/tree"

/** Seitenbaum ab einer Wurzel: Heart, Bereiche, Kapitel, Tag-Seiten, Querschnitt. */
export function PageTree({
  pages,
  root,
}: {
  pages: WikiPage[]
  root: WikiPage
}) {
  return (
    <ul className="flex flex-col gap-2">
      <TreeNode page={root} pages={pages} />
    </ul>
  )
}

function TreeNode({ page, pages }: { page: WikiPage; pages: WikiPage[] }) {
  const kids = childrenOf(pages, page.page_id)
  const linked = linkedQuerschnitt(pages, page.page_id)
  return (
    <li className="flex flex-col gap-2">
      <PageRow page={page} />
      {linked.length > 0 && (
        <p className="pl-6 text-xs text-muted-foreground">
          Verlinkt:{" "}
          {linked.map((other, index) => (
            <Fragment key={other.page_id}>
              {index > 0 && ", "}
              <Link
                to={pageHref(other)}
                className="underline underline-offset-4"
              >
                {other.title}
              </Link>
            </Fragment>
          ))}
        </p>
      )}
      {kids.length > 0 && (
        <ul className="ml-2 flex flex-col gap-2 border-l pl-4">
          {kids.map((child) => (
            <TreeNode key={child.page_id} page={child} pages={pages} />
          ))}
        </ul>
      )}
    </li>
  )
}

export function PageRow({ page }: { page: WikiPage }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge variant={page.kind === "querschnitt" ? "outline" : "secondary"}>
        {KIND_LABEL[page.kind]}
      </Badge>
      <Link
        to={pageHref(page)}
        className="font-medium underline-offset-4 hover:underline"
      >
        {page.title}
      </Link>
      <span className="font-mono text-xs text-muted-foreground">
        {page.page_id}
      </span>
    </div>
  )
}
