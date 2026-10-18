# ADR 0008: Tag-Hierarchie mit Heart-Seite und Navigationssuche

- Status: angenommen
- Datum: 18.10.2026
- Bezug: PRD 7.9, 7.10, F23–F26, Anhang F; ergänzt ADR 0003 und ADR 0005

## Kontext

Das ParlWiki hatte Themen- und Geschäftsseiten, aber keinen Einstieg von oben. Fragen wie „Was sind die Hauptthemen?“ beantwortet keine Volltextsuche. Embeddings sind in Version 1 ausgeschlossen (ADR 0003). Die Forschung zeigt Bäume aus Zusammenfassungen, die von unten nach oben entstehen (RAPTOR, GraphRAG, Clio), und Suchen, die ein LLM durch einen solchen Baum führen (MemWalker, LATTICE, PageIndex). Quellen und Einschränkungen stehen im PRD, Anhang F.

## Entscheid

- **Seitenbaum:** Heart → Bereich → Kapitel → Tag-Seite → Geschäfte, aus dem APS-Schema. Ad-hoc-Tags hängen als Querschnittsthemen unter Heart und werden aus ihren `broader`-Kapiteln verlinkt. Die Tags übernehmen die Rolle, die bei RAPTOR das Clustering mit Embeddings hat.
- **Zusammenfassungen von unten nach oben:** Tag-Seiten aus den Kurzzusammenfassungen ihrer Geschäfte, Eltern-Seiten aus den Zusammenfassungen ihrer Kinder plus Stichproben. Jede Aussage nennt ihre Belege, der Code prüft sie.
- **Seitenstatus:** wie Jobs (`open`, `pending`, `done`, `failed`), mit Schwellen und Weitergabe nach oben, nur bei inhaltlicher Änderung.
- **Navigationssuche:** eine vom Code gesteuerte Schleife wie bei den Workern (ADR 0005). Apertus 8B vergleicht an jedem Knoten alle Kinder in einem Prompt, Apertus 70B wählt am Blatt die Geschäfte und antwortet. Rückweg zum nächstbesten Geschwister, höchstens 8 Schritte, Volltextsuche als Fallback, Suchweg in der Antwort.
- Der Agent nutzt die Navigationssuche als ein Werkzeug (`navigate_tree`).

## Folgen

- Leser und Apertus haben einen Einstieg über Heart; jeder Prompt bleibt klein.
- Die Suche ist nachvollziehbar, weil die Antwort den Suchweg zeigt, und braucht keine Vektorsuche.
- Jedes Geschäft braucht eine Kurzzusammenfassung. Stufe 2 der Klassifikation liefert sie ohne zusätzlichen Aufruf (`summary_de`).
- Seitenläufe kosten Modellaufrufe; Schwellen und Eingabegrenzen halten das klein.
- Die Qualität der Suche hängt an guten Kurzzusammenfassungen. Ein früh falsch gewählter Ast wird durch Rückweg, zwei Äste je Knoten und den Fallback abgefangen; die Trefferquote wird gegen die reine Volltextsuche gemessen.

## Verworfene Alternativen

- **Embeddings und Vektorsuche:** in Version 1 ausgeschlossen (ADR 0003).
- **Agent steuert die Navigation frei:** unvorhersehbare Zahl von Aufrufen und schwer reproduzierbar (ADR 0005).
- **Jede Seite direkt aus allen Geschäften zusammenfassen:** Prompts würden für grosse Kapitel und für Heart zu gross.
- **Jeden Ast einzeln bewerten:** Einzelbewertungen sind unzuverlässig (LATTICE); der Vergleich der Geschwister in einem Prompt ist robuster.
