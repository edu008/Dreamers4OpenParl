import { useMemo, useState } from "react"
import { Link } from "react-router"

import { Confidence } from "@/components/confidence"
import type { TopicRow } from "@/lib/sample-affairs"

type SortKey = "date" | "confidence"
type SortDir = "asc" | "desc"

const LANGUAGE_CODE = { de: "DE", fr: "FR", it: "IT" } as const

function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-")
  return `${day}.${month}.${year}`
}

function SortHeader({
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
      className="px-3 py-2 text-left text-xs font-medium text-muted-foreground"
    >
      <button
        type="button"
        onClick={onSort}
        className="underline-offset-4 hover:underline focus-visible:underline"
      >
        {label}
        {active ? (dir === "asc" ? " ↑" : " ↓") : ""}
      </button>
    </th>
  )
}

// Trefferliste einer Themenseite: eine Zeile je Geschäft, sortierbar nach Datum und Konfidenz.
export function AffairTable({ rows }: { rows: TopicRow[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("date")
  const [sortDir, setSortDir] = useState<SortDir>("desc")

  const sorted = useMemo(() => {
    const factor = sortDir === "asc" ? 1 : -1
    return [...rows].sort((a, b) => {
      const left = sortKey === "date" ? a.affair.date : a.label.confidence
      const right = sortKey === "date" ? b.affair.date : b.label.confidence
      return left < right ? -factor : left > right ? factor : 0
    })
  }, [rows, sortKey, sortDir])

  function sortBy(key: SortKey) {
    if (key === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc")
    } else {
      setSortKey(key)
      setSortDir("desc")
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] border-collapse text-sm">
        <caption className="sr-only">Geschäfte zu diesem Thema</caption>
        <thead className="border-y border-foreground">
          <tr>
            <th scope="col" className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
              Geschäft
            </th>
            <th scope="col" className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
              Parlament
            </th>
            <SortHeader label="Datum" active={sortKey === "date"} dir={sortDir} onSort={() => sortBy("date")} />
            <SortHeader
              label="Konfidenz"
              active={sortKey === "confidence"}
              dir={sortDir}
              onSort={() => sortBy("confidence")}
            />
          </tr>
        </thead>
        <tbody>
          {sorted.map(({ affair, label }) => (
            <tr key={affair.id} className="border-b border-border align-top">
              <td className="max-w-[26rem] px-3 py-3">
                <p className="tabular text-xs text-muted-foreground">
                  {affair.number} · {affair.type} · {LANGUAGE_CODE[affair.language]}
                </p>
                <Link
                  to={`/geschaefte/${affair.id}`}
                  lang={affair.language}
                  className="font-reading text-base leading-snug font-semibold text-foreground underline-offset-4 hover:underline"
                >
                  {affair.title}
                </Link>
              </td>
              <td className="px-3 py-3 text-muted-foreground">{affair.body}</td>
              <td className="tabular px-3 py-3 whitespace-nowrap">{formatDate(affair.date)}</td>
              <td className="px-3 py-3 whitespace-nowrap">
                <Confidence value={label.confidence} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
