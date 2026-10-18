// Leiser Umschalter aus aneinanderliegenden Knöpfen (eine Auswahl, `aria-pressed`). Für Ansicht,
// Grund-Filter und Graph-Ansicht; Auswahl durch Tönung und Gewicht, nicht durch Farbe.
export function Segmented<T extends string>({
  label,
  title,
  options,
  value,
  onChange,
}: {
  /** Name der Gruppe für Screenreader. */
  label: string
  title?: string
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div
      role="group"
      aria-label={label}
      title={title}
      className="inline-flex overflow-hidden rounded-md border border-border text-xs"
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={
            value === option.value
              ? "h-8 bg-secondary px-3 font-medium text-foreground"
              : "h-8 bg-background px-3 text-muted-foreground hover:bg-muted hover:text-foreground"
          }
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
