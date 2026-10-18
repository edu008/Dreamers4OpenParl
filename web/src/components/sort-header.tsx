import type { SortDir } from "@/hooks/use-sort"

const BASE = "px-3 py-2 text-left text-xs font-semibold text-foreground"

/** Spaltenkopf ohne Sortierung. */
export function PlainHeader({ children }: { children: React.ReactNode }) {
  return (
    <th scope="col" className={BASE}>
      {children}
    </th>
  )
}

/** Spaltenkopf mit Sortierknopf. aria-sort sagt Screenreadern, wonach gerade sortiert ist. */
export function SortHeader({
  label,
  active,
  dir,
  onSort,
}: {
  label: string
  active: boolean
  dir: SortDir
  onSort: () => void
}) {
  return (
    <th
      scope="col"
      aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}
      className={BASE}
    >
      <button
        type="button"
        onClick={onSort}
        className="-mx-1 -my-2 whitespace-nowrap px-1 py-2 underline-offset-4 hover:underline focus-visible:underline"
      >
        {label}
        {active ? (dir === "asc" ? " ↑" : " ↓") : ""}
      </button>
    </th>
  )
}
