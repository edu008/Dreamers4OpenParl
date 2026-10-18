import {
  fetchJson,
  type PageTree,
  type TopicAffairs,
  type TopicOut,
  type WikiPage,
} from "@/lib/api"

// Themengraph: Punkte sind Themen mit Geschäften und ihre Bereiche, Linien zeigen die Zugehörigkeit
// zum Bereich und gemeinsame Geschäfte. Übergangslösung: Die Verbindungen werden hier aus den
// Geschäften je Thema berechnet. Mit vielen Geschäften braucht es einen Endpunkt im Backend
// (z. B. GET /v1/graph/topics mit Knoten und Kanten, begrenzt auf eine Höchstzahl).

export interface GraphNode {
  id: string
  label: string
  kind: "bereich" | "thema"
  /** Zahl der Geschäfte (nur Themen). */
  count: number
  /** Bereich, zu dem der Punkt gehört; bestimmt die Farbe. */
  group: string
  x: number
  y: number
}

export interface GraphEdge {
  a: string
  b: string
  kind: "bereich" | "gemeinsam"
  weight: number
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export const WIDTH = 800
export const HEIGHT = 520

interface RawData {
  pages: WikiPage[]
  topics: TopicOut[]
  affairs: Map<string, number[]>
}

async function loadRaw(): Promise<RawData> {
  const [tree, topics] = await Promise.all([
    fetchJson<PageTree>("/v1/pages"),
    fetchJson<TopicOut[]>("/v1/topics"),
  ])
  const withAffairs = topics.filter((topic) => topic.n_affairs > 0)
  const lists = await Promise.all(
    withAffairs.map(async (topic) => {
      const found = await fetchJson<TopicAffairs>(
        `/v1/topics/${encodeURIComponent(topic.tag_id)}/affairs?limit=500`
      )
      return [topic.tag_id, found.items.map((item) => item.affair_id)] as const
    })
  )
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

export function buildGraph(raw: RawData): GraphData {
  const pageById = new Map(raw.pages.map((page) => [page.page_id, page]))
  const nodes = new Map<string, GraphNode>()
  const edges: GraphEdge[] = []

  const topics = raw.topics.filter((topic) => topic.n_affairs > 0)
  for (const topic of topics) {
    const bereich = bereichOf(pageById, topic.tag_id)
    const group = bereich?.page_id ?? "adhoc"
    nodes.set(topic.tag_id, {
      id: topic.tag_id,
      label: topic.name_de,
      kind: "thema",
      count: topic.n_affairs,
      group,
      x: 0,
      y: 0,
    })
    if (bereich) {
      if (!nodes.has(bereich.page_id)) {
        nodes.set(bereich.page_id, {
          id: bereich.page_id,
          label: bereich.title,
          kind: "bereich",
          count: 0,
          group: bereich.page_id,
          x: 0,
          y: 0,
        })
      }
      edges.push({
        a: topic.tag_id,
        b: bereich.page_id,
        kind: "bereich",
        weight: 1,
      })
    }
  }

  // Gemeinsame Geschäfte: zwei Themen tragen dasselbe Geschäft.
  const topicsByAffair = new Map<number, string[]>()
  for (const [tagId, affairIds] of raw.affairs) {
    for (const affairId of affairIds) {
      topicsByAffair.set(affairId, [
        ...(topicsByAffair.get(affairId) ?? []),
        tagId,
      ])
    }
  }
  const pairs = new Map<string, GraphEdge>()
  for (const tagIds of topicsByAffair.values()) {
    for (let i = 0; i < tagIds.length; i++) {
      for (let j = i + 1; j < tagIds.length; j++) {
        const [a, b] = [tagIds[i], tagIds[j]].sort()
        const key = `${a}|${b}`
        const edge = pairs.get(key) ?? {
          a,
          b,
          kind: "gemeinsam" as const,
          weight: 0,
        }
        edge.weight += 1
        pairs.set(key, edge)
      }
    }
  }
  edges.push(...pairs.values())

  const list = [...nodes.values()]
  layout(list, edges)
  return { nodes: list, edges }
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
  const steps = 400
  for (let step = 0; step < steps; step++) {
    const cooling = 1 - step / steps
    for (let i = 0; i < count; i++) {
      for (let j = i + 1; j < count; j++) {
        const dx = nodes[j].x - nodes[i].x
        const dy = nodes[j].y - nodes[i].y
        const distSq = dx * dx + dy * dy + 0.01
        const force = 2600 / distSq
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
      const rest = edge.kind === "bereich" ? 70 : 45
      const dx = b.x - a.x
      const dy = b.y - a.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const pull =
        (dist - rest) *
        (edge.kind === "gemeinsam" ? 0.05 + edge.weight * 0.01 : 0.04)
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
}

/** Farbe je Bereich: gleiche Helligkeit, verschiedene Farbtöne, gut lesbar auf hellem Grund. */
export function groupColor(group: string, groups: string[]): string {
  const index = groups.indexOf(group)
  if (index < 0) return "oklch(0.5 0.02 160)"
  const hue = (index * 360) / Math.max(groups.length, 1)
  return `oklch(0.5 0.12 ${Math.round(hue)})`
}
