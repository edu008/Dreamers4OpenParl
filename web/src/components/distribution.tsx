// Verteilung als waagrechte Balken: Name, Balken, Zahl. Jede Zeile ist ein Knopf, der die Auswahl
// als Filter setzt (nochmals klicken hebt sie auf). Zahlen stehen immer daneben, der Balken ist
// nur Verstärkung.
export interface DistributionRow {
  key: string
  label: string
  count: number
}

export function Distribution({
  title,
  rows,
  activeKey,
  onPick,
  note,
}: {
  title: string
  rows: DistributionRow[]
  activeKey: string | null
  onPick: (key: string | null) => void
  note?: string
}) {
  const max = Math.max(1, ...rows.map((row) => row.count))
  return (
    <section aria-label={title} className="flex flex-col gap-1">
      <h3 className="text-xs font-semibold text-foreground">{title}</h3>
      <ul className="flex flex-col">
        {rows.map((row) => {
          const active = activeKey === row.key
          return (
            <li key={row.key}>
              <button
                type="button"
                aria-pressed={active}
                onClick={() => onPick(active ? null : row.key)}
                className={`grid w-full grid-cols-[8.5rem_1fr_2.5rem] items-center gap-2 py-1.5 text-left text-xs hover:bg-muted ${active ? "bg-secondary font-medium text-foreground" : "text-muted-foreground"}`}
              >
                <span className="truncate" title={row.label}>
                  {row.label}
                </span>
                <span aria-hidden="true" className="h-1.5 bg-border">
                  <span
                    className="block h-full bg-primary"
                    style={{ width: `${(row.count / max) * 100}%` }}
                  />
                </span>
                <span className="tabular text-right text-foreground">
                  {row.count}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      {note && <p className="text-xs text-muted-foreground">{note}</p>}
    </section>
  )
}
