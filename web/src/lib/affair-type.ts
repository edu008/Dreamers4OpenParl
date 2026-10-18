// Die API liefert die Geschäftsart teils englisch. Bis sie eine deutsche Bezeichnung mitgibt,
// übersetzt die Oberfläche die bekannten Arten; Unbekanntes bleibt unverändert.
const TYPE_DE: Record<string, string> = {
  "parliamentary initiative": "Parlamentarische Initiative",
  consultation: "Vernehmlassung",
  postulate: "Postulat",
  motion: "Motion",
  interpellation: "Interpellation",
  "simple question": "Anfrage",
  question: "Frage",
  "question time": "Fragestunde",
  "urgent interpellation": "Dringliche Interpellation",
  "cantonal initiative": "Standesinitiative",
  "popular initiative": "Volksinitiative",
  petition: "Petition",
  "federal council business": "Geschäft des Bundesrates",
  "parliamentary business": "Parlamentarisches Geschäft",
  recommendation: "Empfehlung",
}

export function affairTypeDe(type: string | null): string | null {
  if (type === null) return null
  return TYPE_DE[type.trim().toLowerCase()] ?? type
}
