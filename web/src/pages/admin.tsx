import { JobTable, SystemList } from "@/components/job-summary"

// Admin: Überblick über das System. Verwaltung (Tag-Vorschläge, Themen) folgt, sobald das Backend
// die nötigen Endpunkte hat. Im MVP gibt es keine Zugangskontrolle: /admin ist offen.
export function AdminPage() {
  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
          Admin
        </h1>
        <p className="max-w-[68ch] text-muted-foreground">
          Überblick über das System und die Klassifikation.
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
          Verarbeitungsstand
        </h2>
        <JobTable />
      </section>

      <section
        aria-labelledby="proposals-heading"
        className="flex flex-col gap-2 pt-2"
      >
        <h2 id="proposals-heading" className="font-heading text-lg font-medium">
          Tag-Vorschläge und Themen
        </h2>
        <p className="max-w-[68ch] text-muted-foreground">
          Neue Themen annehmen, zusammenlegen oder ablehnen und Ad-hoc-Themen
          anlegen folgt. Dafür braucht das Backend noch die Endpunkte.
        </p>
      </section>
    </>
  )
}
