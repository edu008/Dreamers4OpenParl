import { JobTable, SystemList } from "@/components/job-summary"

// Verarbeitungsstand als eigene Adresse für Betreiber und den Pitch. Die Hauptnavigation verlinkt
// sie nicht (Council 18.10.2026); der Link steht im Fuss der Seite und unter "Review".
export function StatusPage() {
  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
          Verarbeitungsstand
        </h1>
        <p className="max-w-[68ch] text-muted-foreground">
          Hier sieht man, ob das System läuft und wie weit die Klassifikation
          ist.
        </p>
      </div>

      <section
        aria-labelledby="system-heading"
        className="flex flex-col gap-3 pt-2"
      >
        <h2 id="system-heading" className="font-heading text-lg font-medium">
          System
        </h2>
        <SystemList />
      </section>

      <section
        aria-labelledby="jobs-heading"
        className="flex flex-col gap-3 pt-2"
      >
        <h2 id="jobs-heading" className="font-heading text-lg font-medium">
          Klassifikation
        </h2>
        <JobTable />
      </section>
    </>
  )
}
