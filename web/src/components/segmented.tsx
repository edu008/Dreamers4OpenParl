// Leiser Umschalter (eine Auswahl, `aria-pressed`): eine eingedrückte Clay-Mulde, die Auswahl liegt
// erhaben darin. Auswahl durch Form und Gewicht, nicht durch Farbe.
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
      className="inline-flex flex-wrap gap-1 self-start rounded-3xl bg-muted p-1 text-sm shadow-clay-pressed"
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={
            value === option.value
              ? "h-9 rounded-full bg-card px-3.5 font-semibold text-foreground shadow-clay"
              : "h-9 rounded-full px-3.5 text-muted-foreground transition-colors hover:text-foreground"
          }
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
