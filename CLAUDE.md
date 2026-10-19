# CLAUDE.md – ParlTopics

ParlTopics labelt alle Geschäfte aus OpenParlData mit Themen (festes APS-Schema plus Ad-hoc-Themen) mit Apertus v1.5. Projekt für Hack Apertus Liebefeld, Challenge 2.

- Auftrag (Vorgabe, gilt vor dem PRD): `docs/CHALLENGE.md`
- Was gebaut wird: `docs/PRD.md` (Version 0.4, Hack = Phase 1)
- Wie es gebaut ist: `docs/ARCHITEKTUR.md`, Diagramme in `docs/architecture/`
- Betrieb ohne Internet: `docs/AIRGAP.md`
- Entscheide: `docs/adr/`, Setup und Arbeitsweise: `docs/ENTWICKLUNG.md`

## Auftrag (Kurzfassung, Details in `docs/CHALLENGE.md`)

- **Erfolg:** Qualität auf gelabelter Stichprobe (DVS-Digitalisierung, APS), de/fr/it und alle Ebenen, Ad-hoc-Themen ohne Training, machbare Laufzeit für über 300'000 Geschäfte.
- **Ethik:** Begründung zeigen (Konfidenz, Textstelle), Bias nach Sprache, Region und Partei prüfen, politisch neutral bleiben, Mensch kann korrigieren.
- **Abgabe:** öffentliches Repo mit Open-Source-Lizenz, technischer Bericht (PDF), Demo-Video (max. 2 min), 5-Minuten-Pitch.
- **Bei Zielkonflikten** zählen belegte Zahlen aus der Evaluation mehr als Oberfläche.

## Kommandos

```bash
make setup                 # uv sync
make test                  # Unit-Tests
make lint / make format    # ruff
make db && make migrate    # PostgreSQL im Container, Schema anlegen
make test-integration      # Tests gegen die Datenbank
make api                   # API auf http://127.0.0.1:8000, liefert web/dist aus
make web-dev               # Vite auf http://127.0.0.1:5173 (Web-App mit Hot Reload)
make web-check             # Web-App: Lint, Typprüfung, Build, Prüfung auf externe URLs
make diagrams              # Diagramme mit Archify bauen; make diagrams-check prüft sie
make offline-test          # Image aus Wheels, Test im Docker-Netz ohne Internet
uv run parltopics --help   # CLI mit allen Kommandos
```

## Struktur

- `src/parltopics/`: Paket. `llm/` (Client mit Allowlist), `registry/` (SKOS), `classify/` (Worker), `agent/` (Tool-Calling), `wiki/` (Seitenbaum, Zusammenfassungen), `search/` (Navigationssuche), `api/`, `db.py`, `cli.py`
- `web/`: Web-App (React, Vite, TypeScript, Tailwind CSS, shadcn/ui), Build nach `web/dist`
- `registry/tags.yaml`: einzige Quelle der Tags
- `prompts/`: versionierte Prompts
- `migrations/`: nummerierte SQL-Migrationen
- `deploy/`: Dockerfile, Compose, Air-Gap-Skripte
- `tests/`: `unit/`, `integration/` (braucht `TEST_DATABASE_URL`), `mock_llm/`

## Leitplanken (PRD 10.4)

- **Immer:** nur den Host aus `LLM_BASE_URL` aufrufen (Allowlist im Client), Modell-, Prompt- und Registry-Version an jedem Label, HTML entfernen, Tests vor dem Commit.
- **Vorher fragen:** neue Abhängigkeiten, Schemaänderungen, Änderungen an APS-Einträgen in `registry/tags.yaml`, Änderungen am Exportformat.
- **Nie:** in OpenParlData schreiben, Secrets oder Daten committen, andere Hosts aufrufen, Tag-Vorschläge ohne Review aktivieren, Labels löschen (nur Status ändern), dem Agenten schreibende Werkzeuge geben.

## Konventionen

- Doku auf Deutsch in Schweizer Schreibweise (ss statt ß), Bezeichner im Code auf Englisch.
- Das Template-Layout bleibt: `README.md`, `technical_report.md`, `LICENSE` und `src/` nicht verschieben.
- Worker sind deterministisch, ein Geschäft pro Modellaufruf. Der Agent nutzt Tool-Calling und liest nur.
- Bestehende Migrationen nie ändern, neue Datei anlegen. Geänderte Prompts bekommen ab dem ersten Lauf (M1) eine neue Datei mit höherer Version; bis dahin sind die v1-Dateien Entwürfe (`prompts/README.md`).
- Ändern sich Komponenten oder Abläufe: Quelle in `docs/architecture/src/` anpassen und `make diagrams` ausführen (Skill `archify`).
- Die Web-App lädt nichts von aussen: keine externen Skripte, Schriften oder Stylesheets. shadcn-Komponenten über die CLI hinzufügen (`npx shadcn add`), Systemschriften.
- Tag-Seiten im ParlWiki werden aus der Datenbank erzeugt; Tag-Definitionen stehen nur in `registry/tags.yaml`.
- Commit-Nachrichten auf Englisch im Imperativ.
