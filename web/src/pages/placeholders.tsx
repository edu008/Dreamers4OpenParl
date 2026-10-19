import { Link } from "react-router"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { usePageTitle } from "@/hooks/use-page-title"

export function NotFoundPage() {
  usePageTitle("Seite nicht gefunden")
  return (
    <Alert>
      <AlertTitle>Seite nicht gefunden</AlertTitle>
      <AlertDescription>
        Diese Adresse gibt es in der Web-App nicht.{" "}
        <Link to="/">Zur Suche</Link>
      </AlertDescription>
    </Alert>
  )
}
