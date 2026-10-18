import { Link, NavLink, Outlet, useLocation } from "react-router"

import { RoleSwitch } from "@/components/role-switch"
import { SearchForm } from "@/components/search-form"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useReview } from "@/hooks/use-review"
import { useReviewQueue } from "@/hooks/use-review-queue"
import { buildQueue, openRows } from "@/lib/review-queue"

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
  const { decisions, active, isAdmin } = useReview()
  const queue = useReviewQueue()
  const openReviews = openRows(buildQueue(queue.candidates, decisions)).length

  // Die Navigation folgt der gewählten Ansicht: Review für Reviewer und Admin, Admin nur für Admin.
  const nav = [
    { to: "/", label: "Themen" },
    ...(active ? [{ to: "/review", label: "Review" }] : []),
    ...(isAdmin ? [{ to: "/admin", label: "Admin" }] : []),
    { to: "/graph", label: "Graph" },
    { to: "/hilfe", label: "So funktioniert's" },
  ]

  return (
    <div className="flex min-h-svh flex-col">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 px-6 py-3">
        <Link to="/" className="font-heading text-base font-medium">
          ParlTopics
        </Link>
        <nav aria-label="Hauptnavigation" className="flex flex-wrap gap-1">
          {nav.map((item) => (
            <Button
              key={item.to}
              size="sm"
              variant={isActive(pathname, item.to) ? "secondary" : "ghost"}
              nativeButton={false}
              render={<NavLink to={item.to} end={item.to === "/"} />}
            >
              {item.to === "/review" && active && openReviews > 0
                ? `${item.label} (${openReviews})`
                : item.label}
            </Button>
          ))}
        </nav>
        {/* Auf schmalen Fenstern in eine eigene Zeile, das Suchfeld nimmt den freien Platz. */}
        <div className="flex w-full flex-wrap items-center justify-between gap-x-4 gap-y-2 lg:ml-auto lg:w-auto lg:flex-nowrap">
          {pathname !== "/" && !pathname.startsWith("/suche") && (
            <SearchForm compact />
          )}
          <RoleSwitch />
        </div>
      </header>
      <Separator />
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
