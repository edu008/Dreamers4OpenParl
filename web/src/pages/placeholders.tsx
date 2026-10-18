import { Link } from "react-router"

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
