import { useEffect, useState, type ReactNode } from "react"

import {
  ReviewQueueContext,
  type ReviewQueueState,
} from "@/hooks/use-review-queue"
import {
  fetchJson,
  type PageTree,
  type TopicAffairs,
  type TopicOut,
} from "@/lib/api"
import { pool } from "@/lib/pool"
import { ancestorsOf } from "@/lib/tree"
import { reviewReasons } from "@/lib/label-state"
import type { ReviewCandidate } from "@/lib/review-queue"

// Es gibt noch keinen Endpunkt "Labels mit Prüfbedarf". Übergangslösung: alle Themen mit
// Geschäften laden und die auffälligen Labels hier herausfiltern. Das trägt nur bei wenigen
// Themen; mit mehr Daten braucht es einen Endpunkt im Backend (Auftrag an edu).
async function loadCandidates(signal: AbortSignal): Promise<ReviewCandidate[]> {
  const [topics, tree] = await Promise.all([
    fetchJson<TopicOut[]>("/v1/topics", signal),
    fetchJson<PageTree>("/v1/pages", signal),
  ])
  const withAffairs = topics.filter((topic) => topic.n_affairs > 0)
  const lists = await pool(withAffairs, 8, async (topic) => ({
    topic,
    found: await fetchJson<TopicAffairs>(
      `/v1/topics/${encodeURIComponent(topic.tag_id)}/affairs?limit=500`,
      signal
    ),
  }))
  const areaOf = (tagId: string) => {
    const self = tree.pages.find((page) => page.page_id === tagId)
    const chain = [...ancestorsOf(tree.pages, tagId), ...(self ? [self] : [])]
    return chain.find((page) => page.kind === "bereich") ?? null
  }
  return lists.flatMap(({ topic, found }) => {
    const area = areaOf(topic.tag_id)
    return found.items.flatMap((item) => {
      const reasons = reviewReasons({
        confidence: item.confidence,
        evidence: item.evidence,
        evidenceVerified: item.evidence_verified,
      })
      return reasons.length === 0
        ? []
        : [
            {
              affairId: String(item.affair_id),
              number: item.number,
              title: item.title ?? `Geschäft ${item.affair_id}`,
              body: item.body_name,
              tagId: topic.tag_id,
              labelName: topic.name_de,
              confidence: item.confidence,
              evidence: item.evidence,
              evidenceVerified: item.evidence_verified,
              areaId: area?.page_id ?? null,
              areaName: area?.title ?? null,
              reasons,
            },
          ]
    })
  })
}

export function ReviewQueueProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ReviewQueueState>({
    candidates: [],
    loading: true,
    error: undefined,
  })

  useEffect(() => {
    const controller = new AbortController()
    loadCandidates(controller.signal).then(
      (candidates) =>
        setState({ candidates, loading: false, error: undefined }),
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setState({
            candidates: [],
            loading: false,
            error: error instanceof Error ? error.message : String(error),
          })
        }
      }
    )
    return () => controller.abort()
  }, [])

  return (
    <ReviewQueueContext.Provider value={state}>
      {children}
    </ReviewQueueContext.Provider>
  )
}
