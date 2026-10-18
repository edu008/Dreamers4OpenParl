// Der Ausschnitt eines Suchtreffers (`headline`) ist HTML, in dem die API alles maskiert hat und
// nur die Treffer in <mark> stehen. Statt ihn als HTML einzufügen, zerlegen wir ihn selbst: es
// entstehen nur Text und Treffer, jedes andere Tag bleibt Text.

export interface SnippetPart {
  text: string
  marked: boolean
}

// Die fünf Zeichen, die Python html.escape maskiert.
const ENTITIES: Record<string, string> = {
  "&amp;": "&",
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&#x27;": "'",
}

function unescapeText(text: string): string {
  return text.replace(/&(?:amp|lt|gt|quot|#x27);/g, (entity) => ENTITIES[entity])
}

export function parseSnippet(headline: string): SnippetPart[] {
  const parts: SnippetPart[] = []
  let marked = false
  for (const piece of headline.split(/(<\/?mark>)/)) {
    if (piece === "<mark>") marked = true
    else if (piece === "</mark>") marked = false
    else if (piece !== "") parts.push({ text: unescapeText(piece), marked })
  }
  return parts
}
