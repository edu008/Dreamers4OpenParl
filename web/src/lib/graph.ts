import {
  fetchJson,
  type PageTree,
  type TopicAffairs,
  type TopicOut,
  type WikiPage,
} from "@/lib/api"

// Themengraph in zwei Stufen. Übersicht: ein Punkt je Bereich, die Linien zeigen gemeinsame
// Geschäfte zwischen Bereichen. Ein Klick öffnet einen Bereich und zeigt dessen Themen. So bleibt
// die Zeichnung lesbar, auch wenn viele Themen Geschäfte tragen. Übergangslösung: Die Verbindungen
// werden hier aus den Geschäften je Thema berechnet. Mit mehr Daten braucht es einen Endpunkt im
// Backend (z. B. GET /v1/graph/topics mit Knoten und Kanten).

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
}

/** Platzbedarf eines Punktes samt Beschriftung (Näherung nach Zeichenzahl), Mitte = Punktmitte. */
function box(node: GraphNode): { halfW: number; up: number; down: number } {
  const perChar = node.kind === "bereich" ? 6.6 : 5.4
  return {
    halfW: Math.max(node.r, (node.label.length * perChar) / 2) + 3,
    up: node.r + 2,
    down: node.r + 18,
  }
}

/** Schiebt Punkte auseinander, bis sich keine Beschriftung mehr mit einer anderen überlappt. */
function separate(nodes: GraphNode[]): void {
  for (let pass = 0; pass < 160; pass++) {
    let moved = false
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i]
        const b = nodes[j]
        const ba = box(a)
        const bb = box(b)
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
      const { halfW, up, down } = box(node)
      node.x = Math.min(WIDTH - halfW - 4, Math.max(halfW + 4, node.x))
      node.y = Math.min(HEIGHT - down - 2, Math.max(up + 4, node.y))
    }
    if (!moved) return
  }
}

export interface RawData {
  pages: WikiPage[]
  topics: TopicOut[]
  affairs: Map<string, number[]>
}

/** Führt die Aufgaben mit höchstens `size` gleichzeitigen Anfragen aus. */
async function pool<T, R>(
  items: T[],
  size: number,
  work: (item: T) => Promise<R>
): Promise<R[]> {
  const results = new Array<R>(items.length)
  let next = 0
  async function run(): Promise<void> {
    while (next < items.length) {
      const index = next++
      results[index] = await work(items[index])
    }
  }
  await Promise.all(Array.from({ length: Math.min(size, items.length) }, run))
  return results
}

async function loadRaw(): Promise<RawData> {
  const [tree, topics] = await Promise.all([
    fetchJson<PageTree>("/v1/pages"),
    fetchJson<TopicOut[]>("/v1/topics"),
  ])
  const withAffairs = topics.filter((topic) => topic.n_affairs > 0)
  const lists = await pool(withAffairs, 8, async (topic) => {
    const found = await fetchJson<TopicAffairs>(
      `/v1/topics/${encodeURIComponent(topic.tag_id)}/affairs?limit=500`
    )
    return [topic.tag_id, found.items.map((item) => item.affair_id)] as const
  })
  return { pages: tree.pages, topics, affairs: new Map(lists) }
}

let cache: Promise<RawData> | null = null

export function loadGraphData(): Promise<RawData> {
  if (cache === null) {
    cache = loadRaw().catch((error: unknown) => {
      cache = null
      throw error
    })
  }
  return cache
}

function bereichOf(pages: Map<string, WikiPage>, id: string): WikiPage | null {
  let current = pages.get(id)
  const seen = new Set<string>()
  while (current && !seen.has(current.page_id)) {
    if (current.kind === "bereich") return current
    seen.add(current.page_id)
    current = current.parent_id ? pages.get(current.parent_id) : undefined
  }
  return null
}

function radiusOf(count: number, large: boolean): number {
  return large
    ? 9 + Math.min(20, Math.sqrt(count) * 1.4)
    : 5 + Math.min(14, Math.sqrt(count) * 1.6)
}

/** Paare von Punkten, die dasselbe Geschäft tragen, mit der Zahl der gemeinsamen Geschäfte. */
function pairsOf(membership: Map<number, Set<string>>): GraphEdge[] {
  const pairs = new Map<string, GraphEdge>()
  for (const members of membership.values()) {
    const ids = [...members].sort()
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const key = `${ids[i]}|${ids[j]}`
        const edge = pairs.get(key) ?? { a: ids[i], b: ids[j], weight: 0 }
        edge.weight += 1
        pairs.set(key, edge)
      }
    }
  }
  return [...pairs.values()]
}

/** Behält die stärksten Verbindungen, höchstens etwa drei je Punkt (gleich starke bleiben). */
function strongest(
  edges: GraphEdge[],
  nodeCount: number
): { kept: GraphEdge[]; hidden: number } {
  const limit = Math.max(6, nodeCount * 3)
  if (edges.length <= limit) return { kept: edges, hidden: 0 }
  const sorted = [...edges].sort((a, b) => b.weight - a.weight)
  const cutoff = sorted[limit - 1].weight
  const kept = sorted.filter((edge) => edge.weight >= cutoff)
  return { kept, hidden: edges.length - kept.length }
}

/** Titel einer Seite, z. B. für die Überschrift eines geöffneten Bereichs. */
export function pageTitle(raw: RawData, id: string): string {
  return raw.pages.find((page) => page.page_id === id)?.title ?? id
}

/**
 * Zeichnung zum Stand der Ansicht: ohne `expanded` die Bereiche, mit `expanded` die Themen dieses
 * Bereichs. Themen ohne Bereich (Ad-hoc-Themen) erscheinen in der Übersicht als eigene Punkte.
 */
export function buildView(raw: RawData, expanded: string | null): GraphData {
  const pageById = new Map(raw.pages.map((page) => [page.page_id, page]))
  const topics = raw.topics.filter((topic) => topic.n_affairs > 0)
  const nodes = new Map<string, GraphNode>()
  const membership = new Map<number, Set<string>>()
  const affairsOfNode = new Map<string, Set<number>>()

  for (const topic of topics) {
    const bereich = bereichOf(pageById, topic.tag_id)
    if (expanded !== null && bereich?.page_id !== expanded) continue
    const unitId =
      expanded !== null ? topic.tag_id : (bereich?.page_id ?? topic.tag_id)
    if (!nodes.has(unitId)) {
      nodes.set(unitId, {
        id: unitId,
        label: expanded !== null ? topic.name_de : (bereich?.title ?? topic.name_de),
        kind: expanded === null && bereich ? "bereich" : "thema",
        count: 0,
        group: bereich?.page_id ?? "adhoc",
        r: 0,
        x: 0,
        y: 0,
      })
      affairsOfNode.set(unitId, new Set())
    }
    for (const affairId of raw.affairs.get(topic.tag_id) ?? []) {
      affairsOfNode.get(unitId)!.add(affairId)
      const set = membership.get(affairId) ?? new Set<string>()
      set.add(unitId)
      membership.set(affairId, set)
    }
  }
  for (const node of nodes.values()) {
    node.count = affairsOfNode.get(node.id)!.size
    node.r = radiusOf(node.count, expanded === null)
  }

  const list = [...nodes.values()]
  const { kept, hidden } = strongest(pairsOf(membership), list.length)
  layout(list, kept)
  return { nodes: list, edges: kept, hidden }
}

/** Einfache Kräfteanordnung: Abstossung, Federn entlang der Linien, leichte Zugkraft zur Mitte. */
function layout(nodes: GraphNode[], edges: GraphEdge[]): void {
  const count = nodes.length
  nodes.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / Math.max(count, 1)
    node.x = WIDTH / 2 + Math.cos(angle) * (WIDTH / 3)
    node.y = HEIGHT / 2 + Math.sin(angle) * (HEIGHT / 3)
  })
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const velocity = new Map(nodes.map((node) => [node.id, { x: 0, y: 0 }]))
  const maxWeight = Math.max(1, ...edges.map((edge) => edge.weight))
  // Wenige Punkte bekommen mehr Abstand, damit die Fläche genutzt wird.
  const spread = count <= 12 ? 1.7 : 1
  const steps = 400
  for (let step = 0; step < steps; step++) {
    const cooling = 1 - step / steps
    for (let i = 0; i < count; i++) {
      for (let j = i + 1; j < count; j++) {
        const dx = nodes[j].x - nodes[i].x
        const dy = nodes[j].y - nodes[i].y
        const distSq = dx * dx + dy * dy + 0.01
        const force = (count <= 12 ? 14000 : 6000) / distSq
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
      const rest = (130 - 60 * share) * spread
      const dx = b.x - a.x
      const dy = b.y - a.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const pull = (dist - rest) * (0.015 + 0.04 * share)
      velocity.get(a.id)!.x += (dx / dist) * pull
      velocity.get(a.id)!.y += (dy / dist) * pull
      velocity.get(b.id)!.x -= (dx / dist) * pull
      velocity.get(b.id)!.y -= (dy / dist) * pull
    }
    for (const node of nodes) {
      const v = velocity.get(node.id)!
      v.x += (WIDTH / 2 - node.x) * 0.004
      v.y += (HEIGHT / 2 - node.y) * 0.004
      node.x += v.x * cooling
      node.y += v.y * cooling
      v.x *= 0.82
      v.y *= 0.82
      node.x = Math.min(WIDTH - 60, Math.max(60, node.x))
      node.y = Math.min(HEIGHT - 28, Math.max(28, node.y))
    }
  }
  separate(nodes)
}

/** Farbe je Bereich: gleiche Helligkeit, verschiedene Farbtöne, gut lesbar auf hellem Grund. */
export function groupColor(group: string, groups: string[]): string {
  const index = groups.indexOf(group)
  if (index < 0) return "oklch(0.5 0.02 160)"
  const hue = (index * 360) / Math.max(groups.length, 1)
  return `oklch(0.5 0.12 ${Math.round(hue)})`
}
