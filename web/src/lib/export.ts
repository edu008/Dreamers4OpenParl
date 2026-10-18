import type { TopicAffair } from "@/lib/api"

export const LEVEL_LABEL: Record<string, string> = {
  country: "Bund",
  canton: "Kanton",
  city: "Stadt",
  municipality: "Gemeinde",
}

/** Zelle für CSV: Anführungszeichen verdoppeln und Formelzeichen entschärfen (Tabellenkalkulation). */
function cell(value: string | number | boolean | null | undefined): string {
  let text = value === null || value === undefined ? "" : String(value)
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`
  return /[;"\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

const BOM = String.fromCharCode(0xfeff)

const HEADER = [
  "OpenParlData-ID",
  "Nummer",
  "Titel",
  "Typ",
  "Parlament",
  "Ebene",
  "Datum",
  "Thema",
  "Konfidenz",
  "Beleg im Text gefunden",
  "Beleg",
  "Prüfstufe",
]

/** CSV mit Semikolon (öffnet in Excel mit deutscher Ländereinstellung sauber), UTF-8 mit BOM. */
export function affairsToCsv(rows: TopicAffair[]): string {
  const lines = rows.map((row) =>
    [
      row.affair_id,
      row.number,
      row.title,
      row.type_de ?? row.type,
      row.body_name ?? row.body_key,
      row.body_level ? (LEVEL_LABEL[row.body_level] ?? row.body_level) : "",
      row.begin_date,
      row.name_de,
      row.confidence.toFixed(2),
      row.evidence_verified ? "ja" : "nein",
      row.evidence,
      row.stage === "human" ? "Mensch" : row.stage,
    ]
      .map(cell)
      .join(";")
  )
  const EOL = String.fromCharCode(13, 10)
  return BOM + [HEADER.join(";"), ...lines].join(EOL) + EOL
}

export function downloadText(
  filename: string,
  text: string,
  mime = "text/csv;charset=utf-8"
): void {
  const url = URL.createObjectURL(new Blob([text], { type: mime }))
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
