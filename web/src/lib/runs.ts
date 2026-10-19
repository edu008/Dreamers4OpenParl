// Läufe, Fehler und Gesamtzahlen der Klassifikation (GET /v1/jobs/summary und GET /v1/stats).

export interface RunOut {
  id: number
  task: string
  kind: "full" | "daily" | "adhoc" | "reclassify" | "eval"
  started_at: string
  finished_at: string | null
  n_total: number
  n_done: number
  n_failed: number
  /** An Apertus 70B weitergegeben. */
  n_escalated: number
  prompt_version: string
  registry_version: string
  /** Dauer in Sekunden, bei laufenden Läufen bis jetzt. */
  duration_s: number
  /** Erledigte Geschäfte je Minute. */
  per_minute: number | null
}

export interface JobError {
  task: string
  reason: string
  count: number
}

export interface RunsSummary {
  runs: RunOut[]
  errors: JobError[]
}

export interface Stats {
  affairs: number
  prepared: number
  indexed: number
  classified: number
  labelled: number
  labels: number
  reviewed: number
}

export const RUN_KIND: Record<RunOut["kind"], string> = {
  full: "Volllauf",
  daily: "Tageslauf",
  adhoc: "Ad-hoc",
  reclassify: "Neuklassifikation",
  eval: "Auswertung",
}

/** «2 h 05 min», «12 min» oder «45 s». */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  return `${hours} h ${String(minutes % 60).padStart(2, "0")} min`
}

/** Dauer in Stunden als lesbarer Satzteil: «etwa 5 Stunden», «etwa 3 Tage». */
export function formatHours(hours: number): string {
  if (hours < 1) return "weniger als eine Stunde"
  if (hours < 48) return `etwa ${Math.round(hours)} Stunden`
  return `etwa ${Math.round(hours / 24)} Tage`
}
