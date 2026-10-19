// Umschalter (eine Auswahl, `aria-pressed`): eckige Felder mit schwarzem Rahmen, die Auswahl ist
// schwarz gefüllt. Auswahl durch Füllung und Gewicht, nicht durch Farbe.
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
      className="inline-flex flex-wrap self-start border border-foreground text-sm"
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={
            value === option.value
              ? "h-9 bg-foreground px-3.5 font-bold text-background"
              : "h-9 px-3.5 text-foreground transition-colors hover:bg-muted"
          }
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
