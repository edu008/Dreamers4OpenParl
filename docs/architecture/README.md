# Architektur-Diagramme

Zehn interaktive Diagramme zu ParlTopics, erzeugt mit [Archify](https://github.com/tt-a1i/archify) 3.1.0 (MIT, Commit `b25142d`). Die Quellen liegen als JSON in [`src/`](src/), die HTML-Dateien daneben sind erzeugt.

**Ansehen:** GitHub zeigt bei HTML-Dateien nur den Quelltext. Repo klonen und die Datei im Browser öffnen, z. B. `xdg-open docs/architecture/01-systemarchitektur.html` (Linux), `open …` (macOS) oder per Doppelklick. Die Dateien sind eigenständig: Schrift und Skripte sind eingebettet, beim Öffnen wird nichts aus dem Internet geladen. Eine vereinfachte Übersicht, die GitHub direkt darstellt, steht in [ARCHITEKTUR.md](../ARCHITEKTUR.md#1-überblick).

| Diagramm | Typ | Zeigt |
|---|---|---|
| [01-systemarchitektur](01-systemarchitektur.html) | Architektur | Komponenten mit Web-App (React) und FastAPI, Datenbank, LLM-Endpunkt, Grenze zwischen Rechner mit Internet und Server ohne Internet |
| [02-pipeline](02-pipeline.html) | Workflow | Vom Download bis zur Ausgabe, mit Eskalation an 70B, Vorschlägen, Review und Seitenlauf |
| [03-job-lifecycle](03-job-lifecycle.html) | Lebenszyklus | Status eines Jobs: open, pending (8b und 70b), done, failed, mit Timeout und Neuöffnung |
| [04-worker-sequenz](04-worker-sequenz.html) | Sequenz | Ein Job im Worker: Übernahme, zwei Stufen, Heartbeat, Eskalation, Schreiben mit Besitzprüfung |
| [05-agent-suche](05-agent-suche.html) | Sequenz | Agent-Schleife mit Werkzeugen (auch `navigate_tree`), Zitatprüfung und Protokoll |
| [06-adhoc-thema](06-adhoc-thema.html) | Workflow | Ad-hoc-Thema vom Dialog mit dem Agenten bis zur Aktivierung im Review |
| [07-datenmodell](07-datenmodell.html) | ERD | Alle 24 Tabellen mit Spalten, Schlüsseln und Beziehungen, erzeugt aus `migrations/0001_init.sql` und `0002_wiki_skos.sql` |
| [08-airgap-deployment](08-airgap-deployment.html) | Datenfluss | Online bauen (auch die Web-App mit npm), per Datenträger übertragen, offline betreiben |
| [09-wiki-hierarchie](09-wiki-hierarchie.html) | Baum | Seitenbaum des ParlWiki: Heart, Bereiche, Kapitel, Tag-Seiten, Querschnitt, Geschäfte |
| [10-navigationssuche](10-navigationssuche.html) | Workflow | Navigationssuche durch den Seitenbaum mit Rückweg, Schrittgrenze und Volltext-Fallback |

Die Inhalte sind deutsch. Die Bedienelemente des Viewers (Legend, Export, Route, Lens) sind englisch, weil Archify keinen deutschen Sprachkatalog mitbringt.

## Ändern

1. Quelle in `src/<name>.json` anpassen. Schema und Beispiele: `.claude/skills/archify/schemas/` und `.claude/skills/archify/examples/`. In Claude Code steht dafür der Skill `archify` bereit.
2. `make diagrams` baut alle Diagramme mit `archify finalize` (Schema, Layout, Browser-Check) und aktualisiert `manifest.json`. Findet Archify keinen Browser, zeigt `ARCHIFY_CHROME` auf Chrome oder Chromium.
3. `make diagrams-check` prüft Schema und ob jede HTML-Datei zu ihrer Quelle passt. Die CI führt diesen Check bei jedem Push aus.

Ändert sich `migrations/`, erzeugt `uv run python scripts/erd_from_sql.py` die Quelle `src/07-datenmodell.json` neu; danach `make diagrams`. Tabellen, Spalten und Schlüssel entsprechen 1:1 den Migrationen. Neue Tabellen brauchen einen Platz in `LAYOUT` im Skript.
