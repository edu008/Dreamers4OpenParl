import { Link } from "react-router"

import { useApi } from "@/hooks/use-api"
import type { JobsSummary } from "@/lib/api"

const number = new Intl.NumberFormat("de-CH")

function Section({
  id,
  title,
  children,
}: {
  id: string
  title: string
  children: React.ReactNode
}) {
  return (
    <section aria-labelledby={id} className="flex max-w-[62ch] flex-col gap-2">
      <h2 id={id} className="font-heading text-lg font-medium">
        {title}
      </h2>
      {children}
    </section>
  )
}

// Erklärt in einfachen Worten, was die Oberfläche zeigt. Die Zahl der klassifizierten Geschäfte
// kommt live aus der API, damit der Text nicht veraltet.
export function HelpPage() {
  const jobs = useApi<JobsSummary>("/v1/jobs/summary")
  const done = jobs.data?.tasks.reduce((sum, task) => sum + task.done, 0)
  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
          So funktioniert's
        </h1>
        <p className="max-w-[62ch] text-muted-foreground">
          ParlTopics ordnet Geschäfte der Schweizer Parlamente nach Themen. Hier
          steht, was du auf den Seiten siehst und wie du es lesen kannst.
        </p>
      </div>

      <Section id="what" title="Was ist das?">
        <p>
          Die Geschäfte stammen aus{" "}
          <span className="font-medium">OpenParlData</span>: Bund, Kantone und
          Gemeinden, in Deutsch, Französisch, Italienisch und teils
          Rätoromanisch. Das Sprachmodell Apertus liest jedes Geschäft und
          schlägt Themen vor, ohne dass man das richtige Stichwort kennen muss.
        </p>
      </Section>

      <Section id="label" title="Was ist ein Label?">
        <p>
          Ein Label ist ein <strong>Vorschlag</strong> des Modells: «Dieses
          Geschäft gehört zum Thema Rüstung.» Es ist keine Tatsache. Menschen
          können ein Label bestätigen oder verwerfen. Solange das nicht
          geschehen ist, steht dort «Noch nicht von einem Menschen geprüft».
        </p>
      </Section>

      <Section id="evidence" title="Was ist der Beleg?">
        <p>
          Zu jedem Label zeigt das Modell die Textstelle, auf die es sich
          stützt. Sie ist im Text gelb markiert, damit du selbst prüfen kannst,
          ob das Thema passt. «Beleg im Text gefunden» heisst, dass die Stelle
          wirklich im Geschäft steht. «Beleg nicht im Text gefunden» heisst,
          dass das Modell die Stelle umschrieben hat. Das Label kann trotzdem
          richtig sein, es verdient aber einen zweiten Blick.
        </p>
      </Section>

      <Section id="confidence" title="Was bedeutet die Konfidenz?">
        <p>
          Die Zahl zwischen 0 und 1 ist die Einschätzung des Modells, wie sicher
          es sich ist. Sie ist <strong>keine Wahrscheinlichkeit</strong>: 0.9
          heisst nicht, dass das Label in 90 von 100 Fällen stimmt. Ab 0.8 gilt
          sie als hoch, unter 0.6 als tief. Verlässlicher als die Zahl ist der
          geprüfte Beleg.
        </p>
      </Section>

      <Section id="limits" title="Was du wissen solltest">
        <ul className="flex list-disc flex-col gap-1 pl-5">
          <li>
            Bisher sind erst wenige Geschäfte klassifiziert
            {done !== undefined && (
              <>
                {" "}
                (aktuell <span className="tabular">{number.format(done)}</span>)
              </>
            )}
            . Die Themenübersicht und der Graph werden mit jedem Lauf voller.
          </li>
          <li>
            Die Qualität kann je nach Sprache, Ebene und Parlament
            unterschiedlich sein. Sie wird gemessen und im technischen Bericht
            ausgewiesen.
          </li>
          <li>
            Die Themen beschreiben, <em>worum</em> es in einem Geschäft geht.
            Sie bewerten keine politische Haltung.
          </li>
        </ul>
      </Section>

      <p className="max-w-[62ch] text-sm text-muted-foreground">
        Zurück zu den{" "}
        <Link to="/" className="underline underline-offset-2">
          Themen
        </Link>{" "}
        oder zum{" "}
        <Link to="/graph" className="underline underline-offset-2">
          Graph
        </Link>
        .
      </p>
    </>
  )
}
