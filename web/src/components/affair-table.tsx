import { useMemo } from "react"
import { Link } from "react-router"

import { Confidence } from "@/components/confidence"
import { PlainHeader, SortHeader } from "@/components/sort-header"
import { compareValues, useSort } from "@/hooks/use-sort"
import type { TopicRow } from "@/lib/sample-affairs"

type SortKey = "date" | "confidence"

const LANGUAGE_CODE = { de: "DE", fr: "FR", it: "IT" } as const

function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-")
  return `${day}.${month}.${year}`
}

// Trefferliste einer Themenseite: eine Zeile je Geschäft, sortierbar nach Datum und Konfidenz.
export function AffairTable({ rows }: { rows: TopicRow[] }) {
  const sort = useSort<SortKey>("date", "desc")

  const sorted = useMemo(
    () =>
      [...rows].sort((a, b) =>
        sort.key === "date"
          ? compareValues(a.affair.date, b.affair.date, sort.dir)
          : compareValues(a.label.confidence, b.label.confidence, sort.dir)
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
          {sorted.map(({ affair, label }) => (
            <tr key={affair.id} className="border-b border-border align-top">
              <td className="max-w-[26rem] px-3 py-3">
                <p className="tabular text-xs text-muted-foreground">
                  {affair.number} · {affair.type} ·{" "}
                  {LANGUAGE_CODE[affair.language]}
                </p>
                <Link
                  to={`/geschaefte/${affair.id}`}
                  lang={affair.language}
                  className="text-base leading-snug font-medium text-foreground underline-offset-4 hover:underline"
                >
                  {affair.title}
                </Link>
              </td>
              <td className="px-3 py-3 text-muted-foreground">{affair.body}</td>
              <td className="tabular px-3 py-3 whitespace-nowrap">
                {formatDate(affair.date)}
              </td>
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
