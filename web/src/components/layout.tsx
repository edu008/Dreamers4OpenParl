import { Link, NavLink, Outlet, useLocation } from "react-router"

import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useReview } from "@/hooks/use-review"
import { useReviewQueue } from "@/hooks/use-review-queue"
import { buildQueue, openRows } from "@/lib/review-queue"

// Der Verarbeitungsstand steht bewusst nicht in der Hauptnavigation (Council 18.10.2026).
const NAV = [
  { to: "/", label: "Wiki" },
  { to: "/suche", label: "Suche" },
  { to: "/review", label: "Review" },
  { to: "/graph", label: "Graph" },
]

function isActive(pathname: string, to: string): boolean {
  if (to === "/") {
    return (
      pathname === "/" ||
      pathname.startsWith("/tags/") ||
      pathname.startsWith("/geschaefte/")
    )
  }
  return pathname === to || pathname.startsWith(`${to}/`)
}

export function Layout() {
  const { pathname } = useLocation()
  const { decisions } = useReview()
  const queue = useReviewQueue()
  const openReviews = openRows(buildQueue(queue.candidates, decisions)).length
  return (
    <div className="flex min-h-svh flex-col">
      <header className="flex flex-wrap items-center gap-4 px-6 py-3">
        <Link to="/" className="font-heading text-base font-medium">
          ParlTopics
        </Link>
        <nav aria-label="Hauptnavigation" className="flex flex-wrap gap-1">
          {NAV.map((item) => (
            <Button
              key={item.to}
              size="sm"
              variant={isActive(pathname, item.to) ? "secondary" : "ghost"}
              nativeButton={false}
              render={<NavLink to={item.to} end={item.to === "/"} />}
            >
              {item.to === "/review" && openReviews > 0
                ? `${item.label} (${openReviews})`
                : item.label}
            </Button>
          ))}
        </nav>
      </header>
      <Separator />
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-8">
        <Outlet />
      </main>
      <footer className="px-6 py-6 text-xs text-muted-foreground">
        <Link to="/status" className="underline underline-offset-2">
          Verarbeitungsstand
        </Link>
      </footer>
    </div>
  )
}
