import { useEffect, useMemo, useRef, useState } from "react"
import { Link, useNavigate } from "react-router"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  ALL_TOPICS,
  buildView,
  groupColor,
  loadGraph,
  type ApiGraph,
  type GraphNode,
} from "@/lib/graph"

const SHOWN_LINKS = 12

type View = "bereiche" | "alle"

const VIEWS: { value: View; label: string }[] = [
  { value: "bereiche", label: "Bereiche" },
  { value: "alle", label: "Alle Themen" },
]

// Themengraph: zeigt, welche Themen zusammenhängen. «Bereiche»: ein Punkt je Bereich, ein Klick
// öffnet dessen Themen. «Alle Themen»: alle Punkte auf einmal, Namen nur bei den grössten und
// beim Daraufzeigen. Ein Klick auf ein Thema öffnet dessen Seite.
export function GraphPage() {
  const navigate = useNavigate()
  const [overview, setOverview] = useState<ApiGraph | null>(null)
  const [loaded, setLoaded] = useState<{ key: string; data: ApiGraph } | null>(
    null
  )
  const [error, setError] = useState<string | undefined>()
  const [hovered, setHovered] = useState<string | null>(null)
  const [view, setView] = useState<View>("alle")
  const [expanded, setExpanded] = useState<string | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const changed = useRef(false)

  // Die Übersicht liefert die Bereiche für Farben, Legende und Überschriften.
  useEffect(() => {
    loadGraph(null).then(setOverview, (reason: unknown) =>
      setError(reason instanceof Error ? reason.message : String(reason))
    )
  }, [])

  // Nach dem Wechsel der Ansicht springt der Fokus zur Überschrift, damit Tastatur und
  // Screenreader merken, dass sich etwas geändert hat.
  useEffect(() => {
    if (changed.current) heading.current?.focus()
    changed.current = true
  }, [view, expanded])

  const mode = view === "alle" ? ALL_TOPICS : expanded
  const modeKey = mode ?? ""
  useEffect(() => {
    let current = true
    loadGraph(mode).then(
      (data) => {
        if (current) setLoaded({ key: modeKey, data })
      },
      (reason: unknown) => {
        if (current)
          setError(reason instanceof Error ? reason.message : String(reason))
      }
    )
    return () => {
      current = false
    }
  }, [mode, modeKey])
  const graph = useMemo(
    () =>
      loaded && loaded.key === modeKey
        ? buildView(loaded.data, view === "alle")
        : null,
    [loaded, modeKey, view]
  )
  const groups = useMemo(
    () =>
      (overview?.nodes ?? [])
        .filter((node) => node.kind === "bereich")
        .map((node) => node.id),
    [overview]
  )
  const titleOf = (id: string) =>
    overview?.nodes.find((node) => node.id === id)?.label ?? id
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
  const legend = useMemo(() => {
    const used = new Set((graph?.nodes ?? []).map((node) => node.group))
    return groups.filter((id) => used.has(id))
  }, [graph, groups])

  const opensGroup = (node: GraphNode) =>
    view === "bereiche" && expanded === null && node.kind === "bereich"
  const activate = (node: GraphNode) => {
    if (opensGroup(node)) {
      setHovered(null)
      setExpanded(node.id)
    } else {
      navigate(`/admin/themen/${node.id}`)
    }
  }
  const showLabel = (node: GraphNode) =>
    graph?.labelsAlways ||
    node.hub ||
    (hovered !== null && linkedToHovered.has(node.id))
  const fine = view === "alle"

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
          {view === "bereiche"
            ? "Die Übersicht zeigt die Bereiche. Eine dicke Linie bedeutet, dass zwei Bereiche viele Geschäfte gemeinsam haben. Klicke auf einen Bereich, um seine Themen zu sehen, und auf ein Thema, um dessen Seite zu öffnen."
            : "Jeder Punkt ist ein Thema, die Farbe zeigt den Bereich, die Grösse die Zahl der Geschäfte. Eine Linie bedeutet gemeinsame Geschäfte. Namen stehen bei den grössten Themen und bei dem Punkt, auf den du zeigst."}
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
      {overview && graph && graph.nodes.length > 0 && (
        <>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <div
              role="group"
              aria-label="Ansicht des Graphen"
              className="inline-flex overflow-hidden rounded-md border border-border text-xs"
            >
              {VIEWS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={view === option.value}
                  onClick={() => {
                    setHovered(null)
                    setExpanded(null)
                    setView(option.value)
                  }}
                  className={
                    view === option.value
                      ? "bg-secondary px-3 py-2 font-medium text-foreground"
                      : "bg-background px-3 py-2 text-muted-foreground hover:bg-muted hover:text-foreground"
                  }
                >
                  {option.label}
                </button>
              ))}
            </div>
            <h2
              ref={heading}
              tabIndex={-1}
              className="font-heading text-lg font-medium outline-none"
            >
              {view === "alle"
                ? "Alle Themen"
                : expanded === null
                  ? "Bereiche"
                  : titleOf(expanded)}
            </h2>
            {view === "bereiche" && expanded !== null && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setExpanded(null)}
                >
                  Zurück zur Übersicht
                </Button>
                <Link
                  to={`/admin/themen/${expanded}`}
                  className="py-2 text-sm underline underline-offset-2"
                >
                  Seite des Bereichs öffnen
                </Link>
              </>
            )}
          </div>

          <div className="overflow-x-auto rounded border border-border">
            <svg
              viewBox={`0 0 ${graph.width} ${graph.height}`}
              role="group"
              aria-label={`Themengraph mit ${graph.nodes.length} Punkten und ${graph.edges.length} Linien`}
              className="w-full min-w-[640px] bg-background"
            >
              {graph.edges.map((edge) => {
                const a = byId.get(edge.a)
                const b = byId.get(edge.b)
                if (!a || !b) return null
                const linked =
                  hovered !== null &&
                  linkedToHovered.has(edge.a) &&
                  linkedToHovered.has(edge.b) &&
                  (edge.a === hovered || edge.b === hovered)
                const dim = hovered !== null && !linked
                return (
                  <line
                    key={`${edge.a}|${edge.b}`}
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    stroke={
                      fine && !linked
                        ? "var(--muted-foreground)"
                        : "var(--foreground)"
                    }
                    strokeWidth={
                      fine
                        ? 0.8 + (edge.weight / maxWeight) * 1.6
                        : 1 + (edge.weight / maxWeight) * 7
                    }
                    opacity={
                      fine
                        ? linked
                          ? 0.85
                          : dim
                            ? 0.06
                            : 0.28
                        : dim
                          ? 0.08
                          : 0.35
                    }
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
                    opacity={dim ? 0.2 : 1}
                    className="cursor-pointer outline-none focus-visible:[&>circle:last-of-type]:stroke-[var(--ring)] focus-visible:[&>circle:last-of-type]:stroke-[4px]"
                  >
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={Math.max(node.r, fine ? 9 : 18)}
                      fill="transparent"
                    />
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={node.r}
                      fill={groupColor(node.group, groups)}
                      stroke="var(--background)"
                      strokeWidth={fine ? 1.5 : 2}
                    />
                  </g>
                )
              })}
              {/* Beschriftungen in einer eigenen Ebene über den Punkten, damit sie nie verdeckt sind. */}
              <g pointerEvents="none" aria-hidden="true">
                {graph.nodes.filter(showLabel).map((node) => {
                  const dim = hovered !== null && !linkedToHovered.has(node.id)
                  const strong = opensGroup(node) || node.hub
                  return (
                    <text
                      key={node.id}
                      x={node.x}
                      y={node.y + node.r + 12}
                      textAnchor="middle"
                      fontSize={strong && !fine ? 12 : fine ? 11 : 10.5}
                      fontWeight={strong ? 600 : 400}
                      fill="var(--foreground)"
                      stroke="var(--background)"
                      strokeWidth={3}
                      paintOrder="stroke"
                      opacity={dim ? 0.25 : 1}
                    >
                      {node.label}
                    </text>
                  )
                })}
              </g>
            </svg>
          </div>

          {view === "alle" && legend.length > 0 && (
            <ul
              aria-label="Bereiche"
              className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground"
            >
              {legend.map((id) => (
                <li key={id}>
                  <button
                    type="button"
                    onClick={() => {
                      setView("bereiche")
                      setExpanded(id)
                    }}
                    title="Themen dieses Bereichs einzeln ansehen"
                    className="inline-flex items-center gap-1.5 py-1.5 hover:text-foreground"
                  >
                    <span
                      aria-hidden="true"
                      className="inline-block size-2.5 rounded-full"
                      style={{ background: groupColor(id, groups) }}
                    />
                    {titleOf(id)}
                  </button>
                </li>
              ))}
              {graph.nodes.some((node) => node.group === "adhoc") && (
                <li className="inline-flex items-center gap-1.5 py-1.5">
                  <span
                    aria-hidden="true"
                    className="inline-block size-2.5 rounded-full"
                    style={{ background: groupColor("adhoc", groups) }}
                  />
                  Querschnittsthema (keinem Bereich zugeordnet)
                </li>
              )}
            </ul>
          )}
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
                      to={`/admin/themen/${edge.a}`}
                      className="underline underline-offset-2"
                    >
                      {byId.get(edge.a)?.label}
                    </Link>
                    {" – "}
                    <Link
                      to={`/admin/themen/${edge.b}`}
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
