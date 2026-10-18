# CLAUDE.md – ParlTopics

ParlTopics labelt alle Geschäfte aus OpenParlData mit Themen (festes APS-Schema plus Ad-hoc-Themen) mit Apertus v1.5. Projekt für Hack Apertus Liebefeld, Challenge 2.

- Was gebaut wird: `docs/PRD.md` (Version 0.3, Hack = Phase 1)
- Wie es gebaut ist: `docs/ARCHITEKTUR.md`, Diagramme in `docs/architecture/`
- Betrieb ohne Internet: `docs/AIRGAP.md`
- Entscheide: `docs/adr/`, Setup und Arbeitsweise: `docs/ENTWICKLUNG.md`

## Kommandos

```bash
make setup                 # uv sync
make test                  # Unit-Tests
make lint / make format    # ruff
make db && make migrate    # PostgreSQL im Container, Schema anlegen
make test-integration      # Tests gegen die Datenbank
make api                   # Web-App auf http://127.0.0.1:8000
make diagrams              # Diagramme mit Archify bauen; make diagrams-check prüft sie
make offline-test          # Image aus Wheels, Test im Docker-Netz ohne Internet
uv run parltopics --help   # CLI; nicht umgesetzte Kommandos enden mit Exit-Code 3 und nennen den Meilenstein
```

## Struktur

- `src/parltopics/`: Paket. `llm/` (Client mit Allowlist), `registry/`, `classify/` (Worker), `agent/` (Tool-Calling), `api/`, `db.py`, `cli.py`
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
- Bestehende Migrationen nie ändern, neue Datei anlegen. Geänderte Prompts bekommen eine neue Datei mit höherer Version.
- Ändern sich Komponenten oder Abläufe: Quelle in `docs/architecture/src/` anpassen und `make diagrams` ausführen (Skill `archify`).
- Die Web-App lädt nichts von aussen: keine externen Skripte, Schriften oder Stylesheets.
- Commit-Nachrichten auf Englisch im Imperativ.
