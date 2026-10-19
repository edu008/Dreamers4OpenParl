import { fetchJson } from "@/lib/api"

// Themengraph in zwei Ansichten. Die Knoten und Kanten liefert die API (GET /v1/graph/topics), die
// Anordnung rechnet die Web-App. «Bereiche»: ein Punkt je Bereich, ein Klick öffnet dessen
// Themen. «Alle Themen»: alle Punkte auf einmal, Namen nur bei den grössten Knotenpunkten.

export const WIDTH = 800
export const HEIGHT = 560

export interface GraphNode {
  id: string
  label: string
  kind: "bereich" | "thema"
  /** Zahl der Geschäfte, die der Punkt trägt. */
  count: number
  /** Bereich, zu dem der Punkt gehört; bestimmt die Farbe. */
  group: string
  r: number
  /** Knotenpunkt: bekommt in der Ansicht «Alle Themen» immer eine Beschriftung. */
  hub: boolean
  x: number
  y: number
}

export interface GraphEdge {
  a: string
  b: string
  /** Zahl der Geschäfte, die beide Punkte tragen. */
  weight: number
}

export interface GraphData {
  nodes: GraphNode[]
  /** Nur die stärksten Verbindungen, damit die Zeichnung lesbar bleibt. */
  edges: GraphEdge[]
  /** Zahl der Verbindungen, die aus Platzgründen nicht gezeichnet werden. */
  hidden: number
  width: number
  height: number
  /** Ob alle Punkte dauerhaft beschriftet sind (sonst nur Hubs und der Punkt unter dem Zeiger). */
  labelsAlways: boolean
}

/** Wert für `buildView`: alle Themen auf einmal, Namen nur bei Hubs und beim Daraufzeigen. */
export const ALL_TOPICS = "__alle__"
const HUBS = 12

/** Platzbedarf eines Punktes samt Beschriftung (Näherung nach Zeichenzahl), Mitte = Punktmitte. */
function box(
  node: GraphNode,
  labels: boolean
): { halfW: number; up: number; down: number } {
  // Ohne dauerhafte Beschriftung zählt nur der Punkt, Hubs behalten Platz für ihren Namen.
  if (!labels && !node.hub) {
    return { halfW: node.r + 4, up: node.r + 2, down: node.r + 2 }
  }
  const perChar = node.kind === "bereich" ? 6.6 : 5.4
  return {
    halfW: Math.max(node.r, (node.label.length * perChar) / 2) + 3,
    up: node.r + 2,
    down: node.r + 18,
  }
}

/** Schiebt Punkte auseinander, bis sich keine Beschriftung mehr mit einer anderen überlappt. */
function separate(
  nodes: GraphNode[],
  width: number,
  height: number,
  labels: boolean
): void {
  for (let pass = 0; pass < 160; pass++) {
    let moved = false
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i]
        const b = nodes[j]
        const ba = box(a, labels)
        const bb = box(b, labels)
        const overlapX = ba.halfW + bb.halfW - Math.abs(b.x - a.x)
        const overlapY =
          b.y >= a.y
            ? ba.down + bb.up - (b.y - a.y)
            : bb.down + ba.up - (a.y - b.y)
        if (overlapX <= 0 || overlapY <= 0) continue
        moved = true
        // Entlang der Achse mit dem kleineren Überlapp auseinanderrücken.
        if (overlapX < overlapY) {
          const push = overlapX / 2 + 0.5
          const dir = b.x >= a.x ? 1 : -1
          a.x -= dir * push
          b.x += dir * push
        } else {
          const push = overlapY / 2 + 0.5
          const dir = b.y >= a.y ? 1 : -1
          a.y -= dir * push
          b.y += dir * push
        }
      }
    }
    for (const node of nodes) {
      const { halfW, up, down } = box(node, labels)
      node.x = Math.min(width - halfW - 4, Math.max(halfW + 4, node.x))
      node.y = Math.min(height - down - 2, Math.max(up + 4, node.y))
    }
    if (!moved) return
  }
}

interface ApiNode {
  id: string
  label: string
  kind: string
  count: number
  group: string
}

/** Antwort von GET /v1/graph/topics. */
export interface ApiGraph {
  /** Geöffneter Bereich, `all` oder null in der Übersicht. */
  area: string | null
  nodes: ApiNode[]
  edges: GraphEdge[]
  /** Kanten, die wegen der Höchstzahl fehlen. */
  hidden: number
}

/** Antwort der API mit der Uhrzeit, zu der sie kam («Stand» unter der Zeichnung). */
export interface LoadedGraph {
  graph: ApiGraph
  at: Date
}

// Jeder Klassifikationslauf ändert die Labels. Darum lädt die Seite beim Öffnen frisch
// (forgetGraphs) und merkt sich eine Antwort nur kurz, für den Wechsel zwischen den Ansichten.
const FRESH_MS = 60_000
const cache = new Map<string, { at: number; found: Promise<LoadedGraph> }>()

export function forgetGraphs(): void {
  cache.clear()
}

/** Lädt den Graphen eines Bereichs, `ALL_TOPICS` für alle Themen oder null für die Übersicht. */
export function loadGraph(mode: string | null): Promise<LoadedGraph> {
  const key = mode ?? ""
  const entry = cache.get(key)
  if (entry && Date.now() - entry.at < FRESH_MS) return entry.found
  const params = new URLSearchParams()
  if (mode === ALL_TOPICS) params.set("area", "all")
  else if (mode !== null) params.set("area", mode)
  params.set(
    "limit",
    mode === ALL_TOPICS ? "400" : mode === null ? "60" : "200"
  )
  const found = fetchJson<ApiGraph>(`/v1/graph/topics?${params}`).then(
    (graph) => ({ graph, at: new Date() }),
    (error: unknown) => {
      cache.delete(key)
      throw error
    }
  )
  cache.set(key, { at: Date.now(), found })
  return found
}

function radiusOf(count: number, large: boolean, small = false): number {
  if (small) return 3.5 + Math.min(9, Math.sqrt(count) * 1.1)
  return large
    ? 9 + Math.min(20, Math.sqrt(count) * 1.4)
    : 5 + Math.min(14, Math.sqrt(count) * 1.6)
}

/** Zeichnung aus der Antwort der API: Punkte, Linien und Anordnung. */
export function buildView(api: ApiGraph, all: boolean): GraphData {
  const nodes: GraphNode[] = api.nodes.map((node) => ({
    id: node.id,
    label: node.label,
    kind: node.kind === "bereich" ? "bereich" : "thema",
    count: node.count,
    group: node.group,
    r: radiusOf(node.count, api.area === null, all),
    hub: true,
    x: 0,
    y: 0,
  }))
  if (all) {
    const ranked = [...nodes].sort((a, b) => b.count - a.count)
    ranked.forEach((node, index) => {
      node.hub = index < HUBS
    })
  }
  const width = all ? 1000 : WIDTH
  const height = all ? 680 : HEIGHT
  layout(nodes, api.edges, width, height, !all)
  return {
    nodes,
    edges: api.edges,
    hidden: api.hidden,
    width,
    height,
    labelsAlways: !all,
  }
}

/** Einfache Kräfteanordnung: Abstossung, Federn entlang der Linien, leichte Zugkraft zur Mitte. */
function layout(
  nodes: GraphNode[],
  edges: GraphEdge[],
  width: number,
  height: number,
  labels: boolean
): void {
  const count = nodes.length
  nodes.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / Math.max(count, 1)
    node.x = width / 2 + Math.cos(angle) * (width / 3)
    node.y = height / 2 + Math.sin(angle) * (height / 3)
  })
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const velocity = new Map(nodes.map((node) => [node.id, { x: 0, y: 0 }]))
  const maxWeight = Math.max(1, ...edges.map((edge) => edge.weight))
  // Wenige Punkte bekommen mehr Abstand, damit die Fläche genutzt wird.
  const spread = count <= 12 ? 1.7 : 1
  const degree = new Map<string, number>()
  for (const edge of edges) {
    degree.set(edge.a, (degree.get(edge.a) ?? 0) + 1)
    degree.set(edge.b, (degree.get(edge.b) ?? 0) + 1)
  }
  // Bei vielen Punkten ziehen sich Punkte desselben Bereichs leicht an, damit Gruppen entstehen.
  const grouped = count > 60
  const steps = 400
  for (let step = 0; step < steps; step++) {
    const cooling = 1 - step / steps
    for (let i = 0; i < count; i++) {
      for (let j = i + 1; j < count; j++) {
        const dx = nodes[j].x - nodes[i].x
        const dy = nodes[j].y - nodes[i].y
        const distSq = dx * dx + dy * dy + 0.01
        const force = (count <= 12 ? 14000 : count > 60 ? 7000 : 6000) / distSq
        const dist = Math.sqrt(distSq)
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        velocity.get(nodes[i].id)!.x -= fx
        velocity.get(nodes[i].id)!.y -= fy
        velocity.get(nodes[j].id)!.x += fx
        velocity.get(nodes[j].id)!.y += fy
      }
    }
    for (const edge of edges) {
      const a = byId.get(edge.a)
      const b = byId.get(edge.b)
      if (!a || !b) continue
      const share = edge.weight / maxWeight
      const rest = (130 - 60 * share) * spread * (count > 60 ? 0.55 : 1)
      const dx = b.x - a.x
      const dy = b.y - a.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      // Federn von Punkten mit vielen Linien werden schwächer, sonst schwingt das Layout auf.
      const damp =
        1 / Math.sqrt(Math.max(1, degree.get(a.id) ?? 1, degree.get(b.id) ?? 1))
      const pull = (dist - rest) * (0.015 + 0.04 * share) * damp
      velocity.get(a.id)!.x += (dx / dist) * pull
      velocity.get(a.id)!.y += (dy / dist) * pull
      velocity.get(b.id)!.x -= (dx / dist) * pull
      velocity.get(b.id)!.y -= (dy / dist) * pull
    }
    const centers = new Map<string, { x: number; y: number; n: number }>()
    if (grouped) {
      for (const node of nodes) {
        const c = centers.get(node.group) ?? { x: 0, y: 0, n: 0 }
        c.x += node.x
        c.y += node.y
        c.n += 1
        centers.set(node.group, c)
      }
    }
    for (const node of nodes) {
      const v = velocity.get(node.id)!
      // Punkte ohne Linie sollen nicht an den Rand fliehen.
      const gravity = (degree.get(node.id) ?? 0) === 0 ? 0.03 : 0.004
      v.x += (width / 2 - node.x) * gravity
      v.y += (height / 2 - node.y) * gravity
      const center = grouped ? centers.get(node.group) : undefined
      if (center) {
        v.x += (center.x / center.n - node.x) * 0.012
        v.y += (center.y / center.n - node.y) * 0.012
      }
      const speed = Math.hypot(v.x, v.y)
      if (speed > 12) {
        v.x = (v.x / speed) * 12
        v.y = (v.y / speed) * 12
      }
      node.x += v.x * cooling
      node.y += v.y * cooling
      v.x *= 0.82
      v.y *= 0.82
      node.x = Math.min(width - 30, Math.max(30, node.x))
      node.y = Math.min(height - 28, Math.max(28, node.y))
    }
  }
  separate(nodes, width, height, labels)
}

/** Farbe je Bereich: gleiche Helligkeit, verschiedene Farbtöne, gut lesbar auf hellem Grund. */
export function groupColor(group: string, groups: string[]): string {
  const index = groups.indexOf(group)
  if (index < 0) return "oklch(0.5 0.02 160)"
  const hue = (index * 360) / Math.max(groups.length, 1)
  return `oklch(0.5 0.12 ${Math.round(hue)})`
}
