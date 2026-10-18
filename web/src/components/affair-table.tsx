import { useMemo } from "react"
import { Link } from "react-router"

import { Confidence } from "@/components/confidence"
import { PlainHeader, SortHeader } from "@/components/sort-header"
import { compareValues, useSort } from "@/hooks/use-sort"
import type { TopicAffair } from "@/lib/api"

type SortKey = "date" | "confidence"

function formatDate(iso: string | null): string {
  if (!iso) return ""
  const [year, month, day] = iso.split("-")
  return `${day}.${month}.${year}`
}

// Trefferliste einer Themenseite: eine Zeile je Geschäft, sortierbar nach Datum und Konfidenz.
export function AffairTable({ rows }: { rows: TopicAffair[] }) {
  const sort = useSort<SortKey>("confidence", "desc")

  const sorted = useMemo(
    () =>
      [...rows].sort((a, b) =>
        sort.key === "date"
          ? compareValues(a.begin_date ?? "", b.begin_date ?? "", sort.dir)
          : compareValues(a.confidence, b.confidence, sort.dir)
      ),
    [rows, sort.key, sort.dir]
  )

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[38rem] table-fixed border-collapse text-sm">
        <caption className="sr-only">Geschäfte zu diesem Thema</caption>
        <colgroup>
          <col style={{ width: "42%" }} />
          <col style={{ width: "22%" }} />
          <col style={{ width: "16%" }} />
          <col style={{ width: "20%" }} />
        </colgroup>
        <thead className="border-b border-border bg-margin-tint">
          <tr>
            <PlainHeader>Geschäft</PlainHeader>
            <PlainHeader>Parlament</PlainHeader>
            <SortHeader
              label="Datum"
              active={sort.key === "date"}
              dir={sort.dir}
              onSort={() => sort.sortBy("date", "desc")}
            />
            <SortHeader
              label="Konfidenz"
              active={sort.key === "confidence"}
              dir={sort.dir}
              onSort={() => sort.sortBy("confidence", "desc")}
            />
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.affair_id} className="border-b border-border align-top">
              <td className="px-3 py-3">
                <p className="tabular text-xs text-muted-foreground">
                  {[row.number, row.type].filter(Boolean).join(" · ")}
                </p>
                <Link
                  to={`/geschaefte/${row.affair_id}`}
                  className="text-base leading-snug font-medium text-foreground underline-offset-4 hover:underline"
                >
                  {row.title ?? `Geschäft ${row.affair_id}`}
                </Link>
              </td>
              <td className="px-3 py-3 text-muted-foreground">
                {row.body_name ?? row.body_key}
              </td>
              <td className="tabular px-3 py-3 whitespace-nowrap">
                {formatDate(row.begin_date)}
              </td>
              <td className="px-3 py-3 whitespace-nowrap">
                <Confidence value={row.confidence} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
