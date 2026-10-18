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
| `classify_chapters_v1.md` | Stufe 1: APS-Kapitel wählen | 8B, bei Eskalation 70B |
| `classify_topics_v1.md` | Stufe 2: Themen, Beleg, Vorschläge | 8B, bei Eskalation 70B |
| `adhoc_keywords_v1.md` | Stichwörter DE/FR/IT für ein Ad-hoc-Thema (`generate_keywords`) | 70B |
| `agent_system_v1.md` | Systemprompt des Agenten | 70B |
| `summarize_v1.md` | Zusammenfassung einer Themenseite | 70B |

`tests/unit/test_prompts.py` prüft Kopf, Abschnitte und rendert die Vorlagen mit Testdaten.
