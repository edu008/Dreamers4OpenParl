import { Link } from "react-router"

import { ApiStatus } from "@/components/api-status"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

// Gerüste für die Ansichten aus PRD 7.5; Inhalte folgen in den genannten Meilensteinen.
function Planned({
  title,
  description,
  milestone,
  items,
}: {
  title: string
  description: string
  milestone: string
  items: string[]
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
        <CardAction>
          <Badge variant="outline">{milestone}</Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        <ul className="flex list-disc flex-col gap-1 pl-5">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

export function SearchPage() {
  return (
    <Planned
      title="Suche"
      description="Navigationssuche durch den Seitenbaum, Volltextsuche als Rückfall."
      milestone="M4"
      items={[
        "Je Knoten vergleicht das Modell alle Unterseiten in einem Schritt",
        "Rückweg zum nächstbesten Ast, höchstens acht Schritte",
        "Antwort mit Suchweg und belegten Geschäften, ohne Treffer keine Antwort",
      ]}
    />
  )
}

export function GraphPage() {
  return (
    <Planned
      title="Graph"
      description="Verlinkungen zwischen Tag-Seiten, Kapiteln und Querschnittsthemen."
      milestone="M4"
      items={[
        "Knoten sind Seiten, Kanten sind Hierarchie, Verwandtschaft und gemeinsame Geschäfte",
        "Klick auf einen Knoten öffnet die Seite",
      ]}
    />
  )
}

export function StatusPage() {
  return (
    <>
      <ApiStatus />
      <Planned
        title="Läufe"
        description="Fortschritt der Klassifikation und der Seitenläufe."
        milestone="M3"
        items={[
          "Jobs je Status: open, pending, done, failed",
          "Seiten je Status und Schwelle bis zur nächsten Zusammenfassung",
        ]}
      />
    </>
  )
}

export function NotFoundPage() {
  return (
    <Alert>
      <AlertTitle>Seite nicht gefunden</AlertTitle>
      <AlertDescription>
        Diese Adresse gibt es in der Web-App nicht.{" "}
        <Link to="/">Zum Seitenbaum</Link>
      </AlertDescription>
    </Alert>
  )
}
