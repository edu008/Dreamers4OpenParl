import { Link, NavLink, Outlet, useLocation } from "react-router"

import { ReviewBar } from "@/components/review-bar"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"

const NAV = [
  { to: "/", label: "Wiki" },
  { to: "/suche", label: "Suche" },
  { to: "/review", label: "Review" },
  { to: "/graph", label: "Graph" },
  { to: "/status", label: "Status" },
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
              {item.label}
            </Button>
          ))}
        </nav>
        <div className="ml-auto">
          <ReviewBar />
        </div>
      </header>
      <Separator />
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
