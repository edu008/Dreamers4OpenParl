# Entwicklung

Wie du ParlTopics lokal aufsetzt, testest und änderst. Was gebaut wird, steht im [PRD](PRD.md), wie es gebaut ist, in [ARCHITEKTUR.md](ARCHITEKTUR.md).

## Voraussetzungen

| Werkzeug | Wofür | Version |
|---|---|---|
| Git | Repo | aktuell |
| [uv](https://docs.astral.sh/uv/) | Python, Abhängigkeiten, Kommandos | ≥ 0.5 |
| Docker mit Compose v2 | PostgreSQL, Images, Offline-Test | aktuell |
| make | Abkürzungen | beliebig |
| Node.js mit npm | Web-App (Entwicklung und Build) und Diagramme (Archify) | 22, siehe `web/.nvmrc` |
| Chrome oder Chromium | nur für `make diagrams` (Browser-Check von Archify) | aktuell |

Unter Windows: WSL2 mit aktivierter WSL-Integration in Docker Desktop.

## Setup

```bash
git clone https://github.com/edu008/Dreamers4OpenParl.git
cd Dreamers4OpenParl
make setup          # uv sync: Python 3.12 und alle Abhängigkeiten aus uv.lock
cp .env.example .env # LLM_API_KEY eintragen; LLM_BASE_URL zeigt auf das Keera-Gateway
make db             # PostgreSQL 16 mit pgvector im Container
make migrate        # Schema anlegen
make test           # Unit-Tests
make web-build      # Web-App: npm ci beim ersten Mal, Build nach web/dist
```

Danach:

```bash
uv run parltopics llm check   # erreicht der LLM-Endpunkt beide Modelle?
make api                      # API auf http://127.0.0.1:8000, liefert den Build aus web/dist aus
make web-dev                  # Vite mit Hot Reload auf http://127.0.0.1:5173, /v1 geht an make api
make help                     # alle Ziele
```

## Tests

| Art | Kommando | Braucht |
|---|---|---|
| Unit | `make test` | nichts |
| Integration | `make test-integration` | laufende DB (`make db`); setzt `TEST_DATABASE_URL` |
| Offline | `make offline-test` | Docker; baut Wheels und Image |
| Lint und Format | `make lint`, `make format` | nichts |
| Web-App | `make web-check` | Node 22; ESLint, Typprüfung, Build, Prüfung auf externe URLs |

Integrationstests werden übersprungen, wenn `TEST_DATABASE_URL` fehlt. In CI laufen alle Arten, die Web-App im eigenen Job `web`.

## Arbeitsweise

- **Branches:** `feat/<thema>`, `fix/<thema>`, `docs/<thema>`. Pull Request auf `main`, CI muss grün sein.
- **Commits:** kurze Betreffzeile im Imperativ auf Englisch, wie bisher im Repo (z. B. `Add job queue with SKIP LOCKED`).
- **Pre-Commit:** einmal `uvx pre-commit install`. Danach laufen ruff, Format und die Registry-Prüfung vor jedem Commit.
- **Pull-Request-Checkliste:**
  - [ ] Tests ergänzt, `make lint` und `make test` grün
  - [ ] bei Änderungen in `web/`: `make web-check` grün
  - [ ] PRD oder ARCHITEKTUR.md angepasst, wenn sich Verhalten ändert
  - [ ] Diagramm-Quelle angepasst und `make diagrams` ausgeführt, wenn sich Komponenten oder Abläufe ändern
  - [ ] keine Daten, Gewichte oder Secrets im Commit
  - [ ] [Air-Gap-Checkliste](AIRGAP.md#5-checkliste) erfüllt

## Häufige Änderungen

**Registry (`registry/tags.yaml`):** Felder nach SKOS (PRD 7.2, Anhang A). Im Betrieb ändert sie nur die Web-App bei Review-Aktionen. Von Hand nur bewusst und mit erhöhter `registry_version`, dann `uv run parltopics registry validate` und committen. APS-Einträge nur nach Rücksprache ändern (PRD 10.4).

**Prompts (`prompts/`):** Eine geänderte Fassung bekommt eine neue Datei mit höherer Version (`classify_topics_v2.md`), die alte bleibt für die Nachvollziehbarkeit. `prompt_version` enthält zusätzlich einen Inhalts-Hash, damit stille Änderungen auffallen.

**Datenbank (`migrations/`):** Nie eine bestehende Migration ändern. Neue Datei `000N_<name>.sql`, dann Anhang C im PRD und die Quelle von Diagramm 07 nachziehen.

**Neue Python-Abhängigkeit:** Vorher im Team fragen (PRD 10.4). `uv add <paket>`, dann `make wheels`, um zu prüfen, dass ein passendes Wheel für das Air-Gap-Image existiert.

**Web-App (`web/`):** React mit Vite, TypeScript, Tailwind CSS und shadcn/ui (Base UI, Stil nova). Komponenten kommen über die CLI dazu (`cd web && npx shadcn add <name>`) und werden nicht von Hand kopiert. Farben über die semantischen Tokens (`bg-background`, `text-muted-foreground`), Abstände mit `gap-*`. Daten nur über die Sidecar-API unter `/v1`. Keine Schriften, Skripte oder Bilder von externen Hosts; `make web-build` bricht bei einem neuen Host ab. Eine neue npm-Abhängigkeit erst nach Rücksprache (PRD 10.4), mit geprüfter Lizenz und `npm audit --omit=dev` ohne Befund.

**Seiten und Suche:** Seitenbaum, Schwellen und Weitergabe stehen in `src/parltopics/wiki/tree.py`, die Belegprüfung in `wiki/schemas.py`, die Navigationssuche in `search/navigate.py`. Die Grenzen kommen aus `.env` (`PAGE_*`, `NAVIGATE_*`).

## Diagramme

Quellen liegen in `docs/architecture/src/*.json`, die HTML-Dateien daneben werden erzeugt.

```bash
make diagrams         # alle Diagramme mit Archify bauen (finalize inkl. Browser-Check)
make diagrams-check   # Schema prüfen und kontrollieren, ob die HTML-Dateien zur Quelle passen (läuft in CI)
```

Findet Archify keinen Browser, zeigt `ARCHIFY_CHROME=/pfad/zu/chrome` auf eine Chrome- oder Chromium-Datei. Archify liegt unter `.claude/skills/archify/` und steht in Claude Code auch als Skill zur Verfügung.

## Claude Code im Projekt

- `CLAUDE.md` enthält die Arbeitsregeln für Claude Code in diesem Repo.
- `.claude/settings.json` aktiviert die Plugins ECC, Ponytail und taste-skill für alle im Team.
- ECC bringt den Hook GateGuard mit. Er verlangt vor dem ersten Shell-Befehl einer Sitzung eine kurze Begründung. Abschalten mit `ECC_GATEGUARD=off`.
