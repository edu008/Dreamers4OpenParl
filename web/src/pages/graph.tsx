import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router"

import { Skeleton } from "@/components/ui/skeleton"
import {
  buildGraph,
  groupColor,
  HEIGHT,
  loadGraphData,
  WIDTH,
  type GraphData,
} from "@/lib/graph"

function radius(count: number, kind: "bereich" | "thema"): number {
  return kind === "bereich" ? 9 : 5 + Math.sqrt(count) * 2
}

// Themengraph: zeigt, welche Themen zusammenhängen. Klick auf einen Punkt öffnet die Seite.
export function GraphPage() {
  const navigate = useNavigate()
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [error, setError] = useState<string | undefined>()
  const [hovered, setHovered] = useState<string | null>(null)

  useEffect(() => {
    loadGraphData().then(
      (raw) => setGraph(buildGraph(raw)),
      (reason: unknown) =>
        setError(reason instanceof Error ? reason.message : String(reason))
    )
  }, [])

  const groups = useMemo(
    () => [
      ...new Set(
        (graph?.nodes ?? [])
          .filter((n) => n.kind === "bereich")
          .map((n) => n.id)
      ),
    ],
    [graph]
  )
  const byId = useMemo(
    () => new Map((graph?.nodes ?? []).map((node) => [node.id, node])),
    [graph]
  )
  const shared = (graph?.edges ?? [])
    .filter((edge) => edge.kind === "gemeinsam")
    .sort((a, b) => b.weight - a.weight)
  const linkedToHovered = new Set<string>()
  if (hovered) {
    linkedToHovered.add(hovered)
    for (const edge of graph?.edges ?? []) {
      if (edge.a === hovered) linkedToHovered.add(edge.b)
      if (edge.b === hovered) linkedToHovered.add(edge.a)
    }
  }
  const open = (node: { id: string; kind: "bereich" | "thema" }) =>
    navigate(`/tags/${node.id}`)

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
          Themengraph
        </h1>
        <p className="max-w-[68ch] text-muted-foreground">
          Jeder Punkt ist ein Thema mit Geschäften, die grossen Punkte sind die
          Bereiche. Eine dicke Linie bedeutet, dass zwei Themen dieselben
          Geschäfte tragen. Klicke auf einen Punkt, um die Seite zu öffnen.
        </p>
        <p className="text-xs text-muted-foreground">
          Es sind erst wenige Geschäfte klassifiziert, deshalb ist der Graph
          noch klein.
        </p>
      </div>

      {!graph && !error && <Skeleton className="h-96 w-full" />}
      {error && (
        <p className="text-sm text-destructive">Graph nicht geladen: {error}</p>
      )}
      {graph && graph.nodes.length === 0 && (
        <p className="text-muted-foreground">
          Noch keine klassifizierten Geschäfte, also nichts zu zeichnen.
        </p>
      )}
      {graph && graph.nodes.length > 0 && (
        <>
          <svg
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            role="img"
            aria-label={`Themengraph mit ${graph.nodes.length} Punkten und ${graph.edges.length} Linien`}
            className="w-full rounded border border-border bg-background"
          >
            {graph.edges.map((edge) => {
              const a = byId.get(edge.a)
              const b = byId.get(edge.b)
              if (!a || !b) return null
              const dim =
                hovered !== null &&
                !(linkedToHovered.has(edge.a) && linkedToHovered.has(edge.b))
              return (
                <line
                  key={`${edge.a}|${edge.b}`}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={
                    edge.kind === "gemeinsam"
                      ? "var(--foreground)"
                      : "var(--border)"
                  }
                  strokeWidth={
                    edge.kind === "gemeinsam" ? 1 + edge.weight * 1.5 : 1
                  }
                  opacity={dim ? 0.15 : edge.kind === "gemeinsam" ? 0.7 : 1}
                />
              )
            })}
            {graph.nodes.map((node) => {
              const dim = hovered !== null && !linkedToHovered.has(node.id)
              const r = radius(node.count, node.kind)
              return (
                <g
                  key={node.id}
                  role="link"
                  tabIndex={0}
                  aria-label={`${node.label}${node.kind === "thema" ? `, ${node.count} Geschäfte` : ", Bereich"}`}
                  onClick={() => open(node)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") open(node)
                  }}
                  onMouseEnter={() => setHovered(node.id)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(node.id)}
                  onBlur={() => setHovered(null)}
                  opacity={dim ? 0.25 : 1}
                  className="cursor-pointer outline-none focus-visible:[&>circle]:stroke-[3px]"
                >
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={r}
                    fill={groupColor(node.group, groups)}
                    stroke="var(--background)"
                    strokeWidth={2}
                  />
                  <text
                    x={node.x}
                    y={node.y + r + 12}
                    textAnchor="middle"
                    fontSize={node.kind === "bereich" ? 12 : 10.5}
                    fontWeight={node.kind === "bereich" ? 600 : 400}
                    fill="var(--foreground)"
                    stroke="var(--background)"
                    strokeWidth={3}
                    paintOrder="stroke"
                  >
                    {node.label}
                  </text>
                </g>
              )
            })}
          </svg>

          <section
            aria-labelledby="links-heading"
            className="flex flex-col gap-2"
          >
            <h2 id="links-heading" className="font-heading text-lg font-medium">
              Verbindungen
            </h2>
            {shared.length === 0 ? (
              <p className="text-muted-foreground">
                Noch tragen keine zwei Themen dasselbe Geschäft.
              </p>
            ) : (
              <ul className="flex flex-col gap-1 text-sm">
                {shared.map((edge) => (
                  <li key={`${edge.a}|${edge.b}`}>
                    <Link
                      to={`/tags/${edge.a}`}
                      className="underline underline-offset-2"
                    >
                      {byId.get(edge.a)?.label}
                    </Link>
                    {" – "}
                    <Link
                      to={`/tags/${edge.b}`}
                      className="underline underline-offset-2"
                    >
                      {byId.get(edge.b)?.label}
                    </Link>{" "}
                    <span className="tabular text-muted-foreground">
                      {edge.weight}{" "}
                      {edge.weight === 1
                        ? "gemeinsames Geschäft"
                        : "gemeinsame Geschäfte"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </>
  )
}
