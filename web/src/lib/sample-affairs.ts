// Synthetische Beispieldaten für die Geschäftsseite, bis die Sidecar-API Labels liefert (M3).
// Sie sind erfunden und erscheinen in der Oberfläche als "Beispieldaten". Keine Fremd-URLs im Bundle:
// check-web-dist.mjs lehnt jeden unbekannten Host ab. Echte Quell-Links kommen später aus der API.

export interface AffairLabel {
  tagId: string
  name: string
  confidence: number
  evidence: string | null
  stage: "8b" | "70b" | "human"
}

export interface AffairRecord {
  id: string
  number: string
  type: string
  body: string
  date: string
  language: "de" | "fr" | "it"
  title: string
  paragraphs: string[]
  sourceUrl: string | null
  labels: AffairLabel[]
  model: string
  promptVersion: string
  registryVersion: string
}

export const SAMPLE_AFFAIRS: AffairRecord[] = [
  {
    id: "70435",
    number: "24.3017",
    type: "Motion",
    body: "Bundesversammlung",
    date: "2024-03-14",
    language: "de",
    title: "Sichere E-ID für alle Einwohnerinnen und Einwohner",
    paragraphs: [
      "Der Bundesrat wird beauftragt, eine staatlich anerkannte elektronische Identität zu schaffen, die für Behörden, Unternehmen und Private nutzbar ist.",
      "Dazu gehört, dass die E-ID den digitalen Zugang zu öffentlichen Dienstleistungen ermöglicht, ohne dass die Daten bei privaten Anbietern gespeichert werden.",
    ],
    sourceUrl: null,
    labels: [
      {
        tagId: "beispiel:digitalisierung",
        name: "Digitalisierung (breit)",
        confidence: 0.91,
        evidence: "die E-ID den digitalen Zugang zu öffentlichen Dienstleistungen ermöglicht",
        stage: "8b",
      },
      {
        tagId: "beispiel:datenschutz",
        name: "Datenschutz",
        confidence: 0.64,
        evidence: "ohne dass die Daten bei privaten Anbietern gespeichert werden",
        stage: "8b",
      },
    ],
    model: "apertus-v1-5-8b",
    promptVersion: "v1",
    registryVersion: "2026-10-18.3",
  },
  {
    id: "88120",
    number: "2023-0412",
    type: "Postulat",
    body: "Kanton Genf",
    date: "2023-09-21",
    language: "fr",
    title: "Numérisation des démarches administratives pour les communes",
    paragraphs: [
      "Le Conseil d'État est invité à étudier la mise à disposition d'une plateforme commune permettant aux communes de proposer leurs démarches en ligne.",
      "Une telle plateforme réduirait les coûts et garantirait un niveau de sécurité homogène sur tout le territoire cantonal.",
    ],
    sourceUrl: null,
    labels: [
      {
        tagId: "beispiel:digitalisierung",
        name: "Digitalisierung (breit)",
        confidence: 0.84,
        evidence: "une plateforme commune permettant aux communes de proposer leurs démarches en ligne",
        stage: "8b",
      },
    ],
    model: "apertus-v1-5-8b",
    promptVersion: "v1",
    registryVersion: "2026-10-18.3",
  },
  {
    id: "91007",
    number: "GR 2024/117",
    type: "Interpellation",
    body: "Stadt Zürich",
    date: "2024-06-05",
    language: "de",
    title: "Wartezeiten bei der Veloreparatur-Förderung",
    paragraphs: [
      "Die Stadt unterstützt Reparaturwerkstätten für Velos mit einem jährlichen Beitrag. Wir fragen den Stadtrat nach den Wartezeiten für Antragsstellende.",
    ],
    sourceUrl: null,
    labels: [
      {
        tagId: "beispiel:strassenverkehr",
        name: "Strassenverkehr",
        confidence: 0.52,
        evidence: "Reparaturwerkstätten für Velos",
        stage: "8b",
      },
    ],
    model: "apertus-v1-5-8b",
    promptVersion: "v1",
    registryVersion: "2026-10-18.3",
  },
]

export function findSampleAffair(id: string): AffairRecord | undefined {
  return SAMPLE_AFFAIRS.find((affair) => affair.id === id)
}

// Beispiel-Zuordnung: welche Wiki-Seite welches Beispiel-Label zeigt (nur bis die API Labels liefert).
const SAMPLE_TAG_FOR_PAGE: Record<string, string> = {
  "adhoc:digitalisierung-breit": "beispiel:digitalisierung",
}

export interface TopicRow {
  affair: AffairRecord
  label: AffairLabel
}

export function sampleRowsForPage(pageId: string): TopicRow[] {
  const tagId = SAMPLE_TAG_FOR_PAGE[pageId]
  if (!tagId) return []
  return SAMPLE_AFFAIRS.flatMap((affair) =>
    affair.labels.filter((label) => label.tagId === tagId).map((label) => ({ affair, label }))
  )
}
