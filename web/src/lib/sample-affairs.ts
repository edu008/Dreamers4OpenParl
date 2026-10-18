// Synthetische Beispieldaten für die Geschäftsseite, bis die Sidecar-API Labels liefert (M3).
// Sie sind erfunden und erscheinen in der Oberfläche als "Beispieldaten".

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
  sourceUrl: string
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
    sourceUrl: "https://www.parlament.ch/",
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
    sourceUrl: "https://www.ge.ch/",
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
    sourceUrl: "https://www.stadt-zuerich.ch/",
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
