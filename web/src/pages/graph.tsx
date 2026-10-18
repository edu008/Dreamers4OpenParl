import { useEffect, useMemo, useRef, useState } from "react"
import { Link, useNavigate } from "react-router"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  buildView,
  groupColor,
  HEIGHT,
  loadGraphData,
  pageTitle,
  WIDTH,
  type GraphNode,
  type RawData,
} from "@/lib/graph"

const SHOWN_LINKS = 12

// Themengraph: zeigt, welche Themen zusammenhängen. Die Übersicht zeigt die Bereiche, ein Klick
// öffnet einen Bereich und zeigt dessen Themen, ein weiterer Klick öffnet die Seite des Themas.
export function GraphPage() {
  const navigate = useNavigate()
  const [raw, setRaw] = useState<RawData | null>(null)
  const [error, setError] = useState<string | undefined>()
  const [hovered, setHovered] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const changed = useRef(false)

  useEffect(() => {
    loadGraphData().then(setRaw, (reason: unknown) =>
      setError(reason instanceof Error ? reason.message : String(reason))
    )
  }, [])

  // Nach dem Wechsel der Ansicht springt der Fokus zur Überschrift, damit Tastatur und
  // Screenreader merken, dass sich etwas geändert hat.
  useEffect(() => {
    if (changed.current) heading.current?.focus()
    changed.current = true
  }, [expanded])

  const graph = useMemo(
    () => (raw ? buildView(raw, expanded) : null),
    [raw, expanded]
  )
  const groups = useMemo(
    () =>
      (raw?.pages ?? [])
        .filter((page) => page.kind === "bereich")
        .map((page) => page.page_id),
    [raw]
  )
  const byId = useMemo(
    () => new Map((graph?.nodes ?? []).map((node) => [node.id, node])),
    [graph]
  )
  const maxWeight = Math.max(1, ...(graph?.edges ?? []).map((e) => e.weight))
  const strongestLinks = [...(graph?.edges ?? [])]
    .sort((a, b) => b.weight - a.weight)
    .slice(0, SHOWN_LINKS)
  const linkedToHovered = new Set<string>()
  if (hovered) {
    linkedToHovered.add(hovered)
    for (const edge of graph?.edges ?? []) {
      if (edge.a === hovered) linkedToHovered.add(edge.b)
      if (edge.b === hovered) linkedToHovered.add(edge.a)
    }
  }

  const opensGroup = (node: GraphNode) =>
    expanded === null && node.kind === "bereich"
  const activate = (node: GraphNode) => {
    if (opensGroup(node)) {
      setHovered(null)
      setExpanded(node.id)
    } else {
      navigate(`/tags/${node.id}`)
    }
  }

  return (
    <div
      className="flex flex-col gap-6"
      onKeyDown={(event) => {
        if (event.key === "Escape" && expanded !== null) setExpanded(null)
      }}
    >
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
          Themengraph
        </h1>
        <p className="max-w-[68ch] text-muted-foreground">
          Die Übersicht zeigt die Bereiche. Eine dicke Linie bedeutet, dass zwei
          Bereiche viele Geschäfte gemeinsam haben. Klicke auf einen Bereich, um
          seine Themen zu sehen, und auf ein Thema, um dessen Seite zu öffnen.
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
      {raw && graph && graph.nodes.length > 0 && (
        <>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <h2
              ref={heading}
              tabIndex={-1}
              className="font-heading text-lg font-medium outline-none"
            >
              {expanded === null ? "Bereiche" : pageTitle(raw, expanded)}
            </h2>
            {expanded !== null && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setExpanded(null)}
                >
                  Zurück zur Übersicht
                </Button>
                <Link
                  to={`/tags/${expanded}`}
                  className="py-2 text-sm underline underline-offset-2"
                >
                  Seite des Bereichs öffnen
                </Link>
              </>
            )}
          </div>

          <svg
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            role="group"
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
                  stroke="var(--foreground)"
                  strokeWidth={1 + (edge.weight / maxWeight) * 7}
                  opacity={dim ? 0.08 : 0.35}
                />
              )
            })}
            {graph.nodes.map((node) => {
              const dim = hovered !== null && !linkedToHovered.has(node.id)
              const groupNode = opensGroup(node)
              return (
                <g
                  key={node.id}
                  role={groupNode ? "button" : "link"}
                  tabIndex={0}
                  aria-label={
                    groupNode
                      ? `${node.label}, Bereich, ${node.count} Geschäfte, Themen anzeigen`
                      : `${node.label}, ${node.count} Geschäfte, Seite öffnen`
                  }
                  onClick={() => activate(node)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      activate(node)
                    }
                  }}
                  onMouseEnter={() => setHovered(node.id)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(node.id)}
                  onBlur={() => setHovered(null)}
                  opacity={dim ? 0.25 : 1}
                  className="cursor-pointer outline-none focus-visible:[&>circle:last-of-type]:stroke-[var(--ring)] focus-visible:[&>circle:last-of-type]:stroke-[4px]"
                >
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={Math.max(node.r, 18)}
                    fill="transparent"
                  />
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={node.r}
                    fill={groupColor(node.group, groups)}
                    stroke="var(--background)"
                    strokeWidth={2}
                  />
                  <text
                    x={node.x}
                    y={node.y + node.r + 12}
                    textAnchor="middle"
                    fontSize={groupNode ? 12 : 10.5}
                    fontWeight={groupNode ? 600 : 400}
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
          {graph.hidden > 0 && (
            <p className="text-xs text-muted-foreground">
              Gezeichnet sind die stärksten Verbindungen, {graph.hidden}{" "}
              schwächere sind ausgeblendet.
            </p>
          )}

          <section
            aria-labelledby="links-heading"
            className="flex flex-col gap-2"
          >
            <h2 id="links-heading" className="font-heading text-lg font-medium">
              Stärkste Verbindungen
            </h2>
            {strongestLinks.length === 0 ? (
              <p className="text-muted-foreground">
                Noch tragen keine zwei Punkte dasselbe Geschäft.
              </p>
            ) : (
              <ul className="flex flex-col gap-1 text-sm">
                {strongestLinks.map((edge) => (
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
    </div>
  )
}
