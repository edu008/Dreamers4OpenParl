import { Link, NavLink, Outlet, useLocation } from "react-router"

import { SearchForm } from "@/components/search-form"
import { ThemeSwitch } from "@/components/theme-switch"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { usePageTitle } from "@/hooks/use-page-title"
import { useReview } from "@/hooks/use-review"
import { useReviewQueue } from "@/hooks/use-review-queue"

const STATIC_TITLES: Record<string, string> = {
  "/": "Themen",
  "/admin": "Admin",
  "/admin/review": "Review",
  "/graph": "Graph",
  "/hilfe": "So funktioniert's",
  "/suche": "Suche",
}

// Öffentliche Seite und Admin-Bereich haben je eine eigene Navigation, ohne Links in den anderen Bereich
// ausser «Öffentliche Seite» im Admin.
const PUBLIC_NAV = [
  { to: "/", label: "Themen" },
  { to: "/graph", label: "Graph" },
  { to: "/hilfe", label: "So funktioniert's" },
]
const ADMIN_NAV = [
  { to: "/admin", label: "Übersicht" },
  { to: "/admin/review", label: "Review" },
]

function isActive(pathname: string, to: string): boolean {
  if (to === "/") {
    return (
      pathname === "/" ||
      pathname.startsWith("/tags/") ||
      pathname.startsWith("/geschaefte/")
    )
  }
  if (to === "/admin") return pathname === to
  return pathname === to || pathname.startsWith(`${to}/`)
}

export function Layout() {
  const { pathname } = useLocation()
  const { isAdmin } = useReview()
  // Seiten mit eigenem Titel (Geschäft, Thema) setzen ihn selbst.
  usePageTitle(STATIC_TITLES[pathname])
  const queue = useReviewQueue()
  const openReviews = queue.open.length
  const nav = isAdmin ? ADMIN_NAV : PUBLIC_NAV

  return (
    <div className="flex min-h-svh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-4 focus:z-50 focus:rounded-sm focus:bg-background focus:px-3 focus:py-2 focus:text-sm focus:underline"
      >
        Zum Inhalt springen
      </a>
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 px-6 py-3">
        <Link
          to={isAdmin ? "/admin" : "/"}
          className="font-heading text-base font-medium"
        >
          {isAdmin ? "ParlTopics Admin" : "ParlTopics"}
        </Link>
        <nav aria-label="Hauptnavigation" className="flex flex-wrap gap-1">
          {nav.map((item) => (
            <Button
              key={item.to}
              size="sm"
              variant={isActive(pathname, item.to) ? "secondary" : "ghost"}
              nativeButton={false}
              render={
                <NavLink
                  to={item.to}
                  end={item.to === "/" || item.to === "/admin"}
                />
              }
            >
              {item.to === "/admin/review" && openReviews > 0
                ? `${item.label} (${openReviews})`
                : item.label}
            </Button>
          ))}
        </nav>
        {/* Auf schmalen Fenstern in eine eigene Zeile, das Suchfeld nimmt den freien Platz. */}
        <div className="flex w-full flex-wrap items-center justify-between gap-x-4 gap-y-2 lg:ml-auto lg:w-auto lg:flex-nowrap">
          {isAdmin ? (
            <Link
              to="/"
              className="py-2 text-xs text-muted-foreground underline underline-offset-2"
            >
              Öffentliche Seite
            </Link>
          ) : (
            pathname !== "/" &&
            !pathname.startsWith("/suche") && <SearchForm compact />
          )}
        </div>
      </header>
      <Separator />
      <main
        id="main"
        tabIndex={-1}
        className={`mx-auto flex w-full flex-1 flex-col gap-6 px-6 py-8 outline-none ${pathname === "/admin/review" ? "max-w-6xl" : "max-w-4xl"}`}
      >
        <Outlet />
      </main>
      <footer className="border-t border-border px-6 py-3 text-xs">
        <ThemeSwitch />
      </footer>
    </div>
  )
}
