import { Link, NavLink, Outlet, useLocation } from "react-router"

import { ThemeSwitch } from "@/components/theme-switch"
import { usePageTitle } from "@/hooks/use-page-title"
import { useReview } from "@/hooks/use-review"
import { useReviewQueue } from "@/hooks/use-review-queue"

// Die Startseite und Seiten mit eigenem Titel (Geschäft, Thema) setzen ihn selbst.
const STATIC_TITLES: Record<string, string> = {
  "/admin": "Admin",
  "/admin/review": "Review",
  "/admin/themen": "Themen",
  "/admin/thema-neu": "Ad-hoc-Thema anlegen",
  "/admin/qualitaet": "Qualität",
  "/admin/graph": "Graph",
  "/admin/parlamente": "Parlamente",
  "/hilfe": "So funktioniert's",
}

// Die öffentliche Seite hat eine Aufgabe (Geschäfte finden) und darum kein Menü (Hick's Law).
// Der Admin-Bereich hat seine eigene Navigation und einen Weg zurück zur öffentlichen Seite.
const ADMIN_NAV = [
  { to: "/admin", label: "Übersicht" },
  { to: "/admin/review", label: "Review" },
  { to: "/admin/themen", label: "Themen" },
  { to: "/admin/graph", label: "Graph" },
  { to: "/admin/parlamente", label: "Parlamente" },
  { to: "/admin/qualitaet", label: "Qualität" },
]

function isActive(pathname: string, to: string): boolean {
  if (to === "/admin") return pathname === to
  return pathname === to || pathname.startsWith(`${to}/`)
}

export function Layout() {
  const { pathname } = useLocation()
  const { isAdmin } = useReview()
  usePageTitle(STATIC_TITLES[pathname])
  const openReviews = useReviewQueue().summary?.open ?? 0
  // Ein Raster für Kopf, Inhalt und Fuss: alle beginnen an derselben linken Kante.
  const frame = "mx-auto w-full max-w-6xl px-4 sm:px-8"

  return (
    <div className="flex min-h-svh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-4 focus:z-50 focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:outline-2 focus:outline-ring"
      >
        Zum Inhalt springen
      </a>
      {/* Kopfband in Schweizer Rot über die ganze Breite, Inhalt im Raster. */}
      <header className="bg-primary text-primary-foreground">
        <div
          className={`${frame} flex flex-wrap items-center gap-x-8 gap-y-2 py-4`}
        >
          <Link
            to={isAdmin ? "/admin" : "/"}
            className="font-heading text-xl font-bold tracking-tight focus-visible:outline-primary-foreground"
          >
            ParlTopics
            {isAdmin && <span className="font-normal"> Admin</span>}
          </Link>
          {isAdmin && (
            <>
              <nav aria-label="Admin-Navigation" className="flex flex-wrap">
                {ADMIN_NAV.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/admin"}
                    className={`px-3 py-2 text-sm font-medium focus-visible:outline-primary-foreground ${
                      isActive(pathname, item.to)
                        ? "bg-primary-foreground text-primary"
                        : "hover:bg-primary-hover"
                    }`}
                  >
                    {item.to === "/admin/review" && openReviews > 0
                      ? `${item.label} (${openReviews})`
                      : item.label}
                  </NavLink>
                ))}
              </nav>
              <Link
                to="/"
                className="py-2 text-sm underline-offset-4 hover:underline focus-visible:outline-primary-foreground sm:ml-auto"
              >
                Öffentliche Seite
              </Link>
            </>
          )}
        </div>
      </header>
      <main
        id="main"
        tabIndex={-1}
        className={`${frame} flex flex-1 flex-col gap-10 py-10 outline-none`}
      >
        <Outlet />
      </main>
      <footer className={`${frame} mt-16`}>
        <div className="flex flex-wrap items-center justify-between gap-4 border-t-2 border-foreground py-6 text-sm">
          <Link to="/hilfe" className="underline-offset-4 hover:underline">
            So funktioniert's
          </Link>
          <ThemeSwitch />
        </div>
      </footer>
    </div>
  )
}
