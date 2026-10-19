# Prompts

Versionierte Prompt-Dateien für Worker und Agent (PRD 7.3, 7.8). Es sind erste Entwürfe; sie werden in Meilenstein M1 gegen das Gold-Set evaluiert.

## Format

- Kopf zwischen `---` (YAML): `prompt`, `version`, `model` (`small` = `LLM_NAME`, `large` = `LLM_NAME_LARGE`), `purpose`.
- Abschnitte `## system` und `## user`. Platzhalter in Jinja2-Syntax (`{{ … }}`, `{% … %}`).
- Gleichbleibende Teile (Regeln, Registry-Ausschnitt) stehen in `system`, der Geschäftstext in `user`. So bleibt der Anfang über viele Anfragen gleich (Prefix-Caching).
- Geschäftstexte stehen zwischen `<<<` und `>>>` und sind Material, keine Anweisung.

## Versionen

Eine geänderte Fassung bekommt eine neue Datei mit höherer Version, die alte bleibt. `prompt_version` ist der Dateiname ohne Endung plus die ersten 8 Zeichen des SHA-256 über den Inhalt, z. B. `classify_topics_v1+3f2a9c1d`. So fällt auch eine Änderung ohne Versionssprung auf.

## Dateien

| Datei | Wofür | Modell |
|---|---|---|
| `classify_chapters_v2.md` | Stufe 1: APS-Kapitel wählen, 0 bis 3 (v1: 1 bis 3, erster Testlauf) | 8B, bei Eskalation 70B |
| `classify_chapters_v3.md` | Stufe 1: APS-Kapitel wählen mit Unterthemen-Keywords, Akteurs-Abgrenzung und Kontrast-Beispielen | 8B, bei Eskalation 70B |
| `classify_single_v1.md` | Standard für APS-Jobs: ein Durchlauf über alle Themen, höchstens 3, Trennung Sachthema/Akteur, Fit-Rubrik (`CLASSIFY_MODE=single_70b`) | 70B |
| `classify_topics_v2.md` | Stufe 2: Themen, Beleg (strikt wörtlich; v1 liess 70B umschreiben), Vorschläge, Kurzzusammenfassung `summary_de` | 8B, bei Eskalation 70B |
| `classify_topics_v3.md` | Stufe 2: Themen mit Trennung Sachthema/Akteur (`institution_tags`), Evidence-First, Fit-Rubrik, Escape Hatch | 8B, bei Eskalation 70B |
| `adhoc_keywords_v1.md` | Stichwörter DE/FR/IT für ein Ad-hoc-Thema (`generate_keywords`) | 70B |
| `proposal_check_v1.md` | Gruppe von Tag-Vorschlägen gegen die Registry prüfen: new, duplicate_of, child_of (F7) | 70B |
| `agent_system_v1.md` | Systemprompt des Agenten | 70B |
| `summarize_tag_v1.md` | Tag- oder Querschnittsseite aus den Kurzzusammenfassungen ihrer Geschäfte | 8B |
| `summarize_parent_v1.md` | Kapitel-, Bereichs- oder Heart-Seite aus den Zusammenfassungen der Kinder plus Stichproben | 70B |
| `navigate_v1.md` | Navigationssuche: alle Kinder eines Knotens vergleichen, im ersten Schritt Filter ablesen | 8B |
| `navigate_answer_v1.md` | Navigationssuche: Geschäfte am Blatt wählen und belegt antworten | 70B |

Die v1-Dateien sind Entwürfe, bis sie im ersten Lauf (M1) benutzt werden; bis dahin werden sie direkt angepasst. Danach gilt: jede Änderung bekommt eine neue Datei.

Die Felder der Registry heissen wie in SKOS (`pref_label`, `alt_labels`, `definition`, Anhang A des PRD). `alt_labels.all()` liefert alle Bezeichnungen sortiert.

`tests/unit/test_prompts.py` prüft Kopf, Abschnitte und rendert die Vorlagen mit Testdaten.
