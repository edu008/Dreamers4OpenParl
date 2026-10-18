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
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import type { Health } from "@/lib/api"

export function ApiStatus() {
  const health = useApi<Health>("/healthz")
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>API</CardTitle>
        <CardDescription>
          FastAPI mit Health-Check unter /healthz
        </CardDescription>
        <CardAction>
          {health.loading && <Skeleton className="h-5 w-24" />}
          {health.data && (
            <Badge variant="secondary">
              erreichbar · {health.data.version}
            </Badge>
          )}
          {health.error && (
            <Badge variant="destructive">nicht erreichbar</Badge>
          )}
        </CardAction>
      </CardHeader>
      {health.error && (
        <CardContent>
          <Alert variant="destructive">
            <AlertTitle>Die API antwortet nicht</AlertTitle>
            <AlertDescription>
              {health.error}. Für die Entwicklung zuerst „make api“ starten,
              dann „make web-dev“.
            </AlertDescription>
          </Alert>
        </CardContent>
      )}
    </Card>
  )
}
