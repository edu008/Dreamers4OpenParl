import { Fragment } from "react"

// Markiert die Belegstellen im Originaltext. Gefunden wird nur, was wörtlich im Absatz steht
// (nach Vereinheitlichung der Leerzeichen); alles andere gilt als "nicht im Text gefunden".

export interface EvidenceSpan {
  key: string
  text: string
}

interface Segment {
  text: string
  evidenceKey?: string
}

function normalizeSpaces(value: string): string {
  return value.replace(/\s+/g, " ").trim()
}

export function findEvidence(paragraph: string, evidence: string): [number, number] | null {
  const needle = normalizeSpaces(evidence)
  if (!needle) return null
  const start = paragraph.indexOf(needle)
  return start === -1 ? null : [start, start + needle.length]
}

export function isEvidenceFound(paragraphs: string[], evidence: string): boolean {
  return paragraphs.some((paragraph) => findEvidence(paragraph, evidence) !== null)
}

export function segmentParagraph(paragraph: string, spans: EvidenceSpan[]): Segment[] {
  const hits = spans
    .map((span) => ({ span, range: findEvidence(paragraph, span.text) }))
    .filter((hit): hit is { span: EvidenceSpan; range: [number, number] } => hit.range !== null)
    .sort((a, b) => a.range[0] - b.range[0])
  const segments: Segment[] = []
  let cursor = 0
  for (const { span, range } of hits) {
    if (range[0] < cursor) continue // überlappende Belege: der erste gewinnt
    if (range[0] > cursor) segments.push({ text: paragraph.slice(cursor, range[0]) })
    segments.push({ text: paragraph.slice(range[0], range[1]), evidenceKey: span.key })
    cursor = range[1]
  }
  if (cursor < paragraph.length) segments.push({ text: paragraph.slice(cursor) })
  return segments
}

export function EvidenceText({
  paragraph,
  spans,
  lang,
}: {
  paragraph: string
  spans: EvidenceSpan[]
  lang: string
}) {
  return (
    <p lang={lang} className="font-reading text-[1.0625rem] leading-[1.7]">
      {segmentParagraph(paragraph, spans).map((segment, index) => (
        <Fragment key={index}>
          {segment.evidenceKey ? (
            <mark
              id={`evidence-${segment.evidenceKey}`}
              className="bg-evidence px-0.5 text-foreground shadow-[inset_0_-2px_0_var(--evidence-line)]"
            >
              {segment.text}
            </mark>
          ) : (
            segment.text
          )}
        </Fragment>
      ))}
    </p>
  )
}
