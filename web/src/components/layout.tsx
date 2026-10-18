import { Link, NavLink, Outlet, useLocation } from "react-router"

import { ThemeSwitch } from "@/components/theme-switch"
import { Button } from "@/components/ui/button"
import { usePageTitle } from "@/hooks/use-page-title"
import { useReview } from "@/hooks/use-review"
import { useReviewQueue } from "@/hooks/use-review-queue"

// Die Startseite und Seiten mit eigenem Titel (Geschäft, Thema) setzen ihn selbst.
const STATIC_TITLES: Record<string, string> = {
  "/admin": "Admin",
  "/admin/review": "Review",
  "/admin/themen": "Themen",
  "/admin/graph": "Graph",
  "/hilfe": "So funktioniert's",
}

// Die öffentliche Seite hat eine Aufgabe (Geschäfte finden) und darum kein Menü (Hick's Law).
// Der Admin-Bereich hat seine eigene Navigation und einen Weg zurück zur öffentlichen Seite.
const ADMIN_NAV = [
  { to: "/admin", label: "Übersicht" },
  { to: "/admin/review", label: "Review" },
  { to: "/admin/themen", label: "Themen" },
  { to: "/admin/graph", label: "Graph" },
]

function isActive(pathname: string, to: string): boolean {
  if (to === "/admin") return pathname === to
  return pathname === to || pathname.startsWith(`${to}/`)
}

export function Layout() {
  const { pathname } = useLocation()
  const { isAdmin } = useReview()
  usePageTitle(STATIC_TITLES[pathname])
  const queue = useReviewQueue()
  const openReviews = queue.open.length
  // Ein Raster für Kopf, Inhalt und Fuss: alle beginnen an derselben linken Kante.
  const frame = `mx-auto w-full px-4 sm:px-8 ${pathname === "/admin/review" ? "max-w-6xl" : "max-w-5xl"}`

  return (
    <div className="flex min-h-svh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-4 focus:z-50 focus:rounded-full focus:bg-card focus:px-4 focus:py-2 focus:text-sm focus:shadow-clay"
      >
        Zum Inhalt springen
      </a>
      <header
        className={`${frame} flex flex-wrap items-center gap-x-6 gap-y-3 pt-6 pb-2`}
      >
        <Link
          to={isAdmin ? "/admin" : "/"}
          className="font-heading text-lg font-bold tracking-tight"
        >
          ParlTopics
          {isAdmin && <span className="font-normal"> Admin</span>}
        </Link>
        {isAdmin && (
          <>
            <nav
              aria-label="Admin-Navigation"
              className="flex flex-wrap gap-1 rounded-full bg-muted p-1 shadow-clay-pressed"
            >
              {ADMIN_NAV.map((item) => (
                <Button
                  key={item.to}
                  size="sm"
                  variant={isActive(pathname, item.to) ? "outline" : "ghost"}
                  nativeButton={false}
                  render={<NavLink to={item.to} end={item.to === "/admin"} />}
                >
                  {item.to === "/admin/review" && openReviews > 0
                    ? `${item.label} (${openReviews})`
                    : item.label}
                </Button>
              ))}
            </nav>
            <Link
              to="/"
              className="py-2 text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline sm:ml-auto"
            >
              Öffentliche Seite
            </Link>
          </>
        )}
      </header>
      <main
        id="main"
        tabIndex={-1}
        className={`${frame} flex flex-1 flex-col gap-8 py-8 outline-none`}
      >
        <Outlet />
      </main>
      <footer className="mt-16 bg-muted">
        <div
          className={`${frame} flex flex-wrap items-center justify-between gap-4 py-6 text-sm`}
        >
          <Link to="/hilfe" className="underline-offset-4 hover:underline">
            So funktioniert's
          </Link>
          <ThemeSwitch />
        </div>
      </footer>
    </div>
  )
}
