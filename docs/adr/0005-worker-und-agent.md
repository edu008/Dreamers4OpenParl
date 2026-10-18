# ADR 0005: Deterministische Worker für den Bestand, Tool-Calling-Agent für den Dialog

- Status: angenommen
- Datum: 18.10.2026
- Bezug: PRD 1, 7.3, 7.8, F5, F21, ARCHITEKTUR.md 3 und 4

## Kontext

ParlTopics nutzt Apertus für zwei sehr verschiedene Aufgaben. Die Massenklassifikation verarbeitet 326'000 Geschäfte und muss billig, wiederaufnehmbar und reproduzierbar sein. Suche und das Anlegen von Ad-hoc-Themen sind interaktiv, selten und brauchen mehrere Schritte, deren Reihenfolge von der Anfrage abhängt.

## Entscheid

- **Worker** für die Klassifikation: Der Code steuert Reihenfolge und Status, Apertus 8B (bei Unsicherheit 70B) bekommt genau ein Geschäft mit festem Prompt und liefert JSON. Kein Tool-Calling.
- **Agent** für Suche und Ad-hoc-Dialog: Apertus 70B wählt lesende Werkzeuge über Tool-Calling, höchstens 6 Aufrufe, jede Aussage mit IDs aus Werkzeug-Ergebnissen belegt. Schreiben kann nur ein Mensch nach Bestätigung im UI.

## Folgen

- Die teure, kritische Massenverarbeitung bleibt vorhersehbar und testbar.
- Der Agent ist flexibel, aber eng begrenzt: nur lesend, Schrittgrenze, Zitatprüfung, Protokoll in `agent_runs`.
- Unterstützt der Endpunkt kein Tool-Calling, nutzt der Agent ein Prompt-Protokoll mit denselben Pydantic-Modellen.

## Verworfene Alternativen

- **Ein Agent für alles:** pro Geschäft mehrere Modellaufrufe mit unvorhersehbarer Zahl, schwer reproduzierbar, mit 8B unzuverlässig.
- **Kein Agent, nur feste Suche:** natürlichsprachige Anfragen und der Ad-hoc-Dialog wären nur mit starren Formularen möglich.
