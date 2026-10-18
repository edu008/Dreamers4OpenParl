import { Link } from "react-router"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

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
