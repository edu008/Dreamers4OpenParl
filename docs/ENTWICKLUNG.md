# Entwicklung

Wie du ParlTopics lokal aufsetzt, testest und änderst. Was gebaut wird, steht im [PRD](PRD.md), wie es gebaut ist, in [ARCHITEKTUR.md](ARCHITEKTUR.md).

## Voraussetzungen

| Werkzeug | Wofür | Version |
|---|---|---|
| Git | Repo | aktuell |
| [uv](https://docs.astral.sh/uv/) | Python, Abhängigkeiten, Kommandos | ≥ 0.5 |
| Docker mit Compose v2 | PostgreSQL, Images, Offline-Test | aktuell |
| make | Abkürzungen | beliebig |
| Node.js | nur für Diagramme (Archify) | ≥ 18 |
| Chrome oder Chromium | nur für `make diagrams` (Browser-Check von Archify) | aktuell |

Unter Windows: WSL2 mit aktivierter WSL-Integration in Docker Desktop.

## Setup

```bash
git clone https://github.com/edu008/Dreamers4OpenParl.git
cd Dreamers4OpenParl
make setup          # uv sync: Python 3.12 und alle Abhängigkeiten aus uv.lock
cp .env.example .env # LLM_NAME, LLM_NAME_LARGE, LLM_BASE_URL, LLM_API_KEY eintragen
make db             # PostgreSQL 16 mit pgvector im Container
make migrate        # Schema anlegen
make data           # OpenParlData laden (~6 GB, inkl. Dokumente) und importieren
make test           # Unit-Tests
```

`make data` lädt Parlamente, Geschäfte, Texte und Dokumente nach `data/import` und importiert sie. Ein zweiter Lauf lädt und schreibt nur, was sich geändert hat. Nur einzelne Parlamente: `uv run parltopics download --bodies CHE --bodies ZH`.

Danach:

```bash
uv run parltopics llm check   # erreicht der LLM-Endpunkt beide Modelle?
make api                      # Web-App und API auf http://127.0.0.1:8000
make help                     # alle Ziele
```

## Gemeinsame Datenbank über Tailscale

Eine Person betreibt die Datenbank mit allen Daten (`make db`, `make migrate`, `make data`), die anderen greifen über [Tailscale](https://tailscale.com) darauf zu. Tailscale ist ein privates Netz nur für das Team: Kein Port ist im Internet offen, und der Router muss nicht eingestellt werden. Die Datenbank bleibt an `127.0.0.1` gebunden; `tailscale serve` reicht den Port nur ins Team-Netz weiter.

**Wer die Datenbank betreibt (einmalig):**

1. Tailscale installieren (`brew install --cask tailscale` oder von tailscale.com), starten und anmelden.
2. Im Tailscale-Admin unter „Users“ die Kollegen einladen.
3. In `.env` ein starkes `POSTGRES_PASSWORD` setzen und `DATABASE_URL` anpassen. Bei einer bestehenden Datenbank zusätzlich: `docker exec -it parltopics-db-1 psql -U parltopics -c "\password parltopics"`.
4. Port im Team-Netz freigeben; die Freigabe bleibt nach einem Neustart bestehen:

   ```bash
   tailscale serve --bg --tcp 5432 tcp://localhost:5432
   tailscale status   # Name des Rechners, z. B. mdni-macbook
   ```

   Beenden: `tailscale serve --tcp 5432 off`.

**Wer mitarbeitet:**

1. Tailscale installieren, die Einladung annehmen und anmelden.
2. In `.env` die gemeinsame Datenbank eintragen. Das Passwort gibt es von der betreibenden Person über einen sicheren Kanal (Passwort-Manager, Signal), nie im Repo oder Chat-Verlauf:

   ```bash
   DATABASE_URL=postgresql://parltopics:<passwort>@<rechnername>:5432/parltopics
   ```

3. Prüfen: `uv run python -c "from parltopics.config import Settings; import psycopg; print(psycopg.connect(Settings().database_url).execute('select count(*) from affairs').fetchone())"`. Kein eigenes `make db` nötig.

Die Datenbank ist nur erreichbar, solange der Rechner der betreibenden Person läuft. `make migrate` und `make data` führt nur sie aus, damit nicht zwei Personen gleichzeitig das Schema ändern.

## Tests

| Art | Kommando | Braucht |
|---|---|---|
| Unit | `make test` | nichts |
| Integration | `make test-integration` | laufende DB (`make db`); setzt `TEST_DATABASE_URL` |
| Offline | `make offline-test` | Docker; baut Wheels und Image |
| Lint und Format | `make lint`, `make format` | nichts |

Integrationstests werden übersprungen, wenn `TEST_DATABASE_URL` fehlt. In CI laufen alle drei Arten.

## Arbeitsweise

- **Branches:** `feat/<thema>`, `fix/<thema>`, `docs/<thema>`. Pull Request auf `main`, CI muss grün sein.
- **Commits:** kurze Betreffzeile im Imperativ auf Englisch, wie bisher im Repo (z. B. `Add job queue with SKIP LOCKED`).
- **Pre-Commit:** einmal `uvx pre-commit install`. Danach laufen ruff, Format und die Registry-Prüfung vor jedem Commit.
- **Pull-Request-Checkliste:**
  - [ ] Tests ergänzt, `make lint` und `make test` grün
  - [ ] PRD oder ARCHITEKTUR.md angepasst, wenn sich Verhalten ändert
  - [ ] Diagramm-Quelle angepasst und `make diagrams` ausgeführt, wenn sich Komponenten oder Abläufe ändern
  - [ ] keine Daten, Gewichte oder Secrets im Commit
  - [ ] [Air-Gap-Checkliste](AIRGAP.md#5-checkliste) erfüllt

## Häufige Änderungen

**Registry (`registry/tags.yaml`):** Im Betrieb ändert sie nur die Web-App bei Review-Aktionen. Von Hand nur bewusst und mit erhöhter `registry_version`, dann `uv run parltopics registry validate` und committen. APS-Einträge nur nach Rücksprache ändern (PRD 10.4).

**Prompts (`prompts/`):** Eine geänderte Fassung bekommt eine neue Datei mit höherer Version (`classify_topics_v2.md`), die alte bleibt für die Nachvollziehbarkeit. `prompt_version` enthält zusätzlich einen Inhalts-Hash, damit stille Änderungen auffallen.

**Datenbank (`migrations/`):** Nie eine bestehende Migration ändern. Neue Datei `000N_<name>.sql`, dann Anhang C im PRD und die Quelle von Diagramm 07 nachziehen.

**Neue Python-Abhängigkeit:** Vorher im Team fragen (PRD 10.4). `uv add <paket>`, dann `make wheels`, um zu prüfen, dass ein passendes Wheel für das Air-Gap-Image existiert.

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
