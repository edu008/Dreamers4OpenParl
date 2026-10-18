import { ApiStatus } from "@/components/api-status"
import { PageTree } from "@/components/page-tree"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/use-api"
import type { PageTree as PageTreeData } from "@/lib/api"
import { HEART_ID } from "@/lib/tree"

export function HomePage() {
  const tree = useApi<PageTreeData>("/v1/pages")
  const heart = tree.data?.pages.find((page) => page.page_id === HEART_ID)
  return (
    <>
      <div className="flex flex-col gap-1">
        <h1 className="font-heading text-2xl font-medium">ParlWiki</h1>
        <p className="text-muted-foreground">
          Themen der Geschäfte in OpenParlData, geordnet von Heart über Bereiche
          und Kapitel bis zu den Tag-Seiten.
        </p>
      </div>
      <ApiStatus />
      <Card>
        <CardHeader>
          <CardTitle>Seitenbaum</CardTitle>
          <CardDescription>
            {tree.data
              ? `Registry ${tree.data.registry_version} · ${tree.data.pages.length} Seiten`
              : "Aus registry/tags.yaml"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {tree.loading && (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-5 w-64" />
              <Skeleton className="h-5 w-56" />
            </div>
          )}
          {tree.error && (
            <Alert variant="destructive">
              <AlertTitle>Seitenbaum nicht geladen</AlertTitle>
              <AlertDescription>{tree.error}</AlertDescription>
            </Alert>
          )}
          {tree.data && heart && (
            <PageTree pages={tree.data.pages} root={heart} />
          )}
        </CardContent>
        <CardFooter>
          <p className="text-xs text-muted-foreground">
            Zusammenfassungen, Kennzahlen und Geschäftslisten der Seiten folgen
            in Meilenstein M3. Die APS-Codes kommen mit dem Import in M0.
          </p>
        </CardFooter>
      </Card>
    </>
  )
}
