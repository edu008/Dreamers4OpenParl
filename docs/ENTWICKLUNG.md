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

Unter Windows: WSL2 mit aktivierter WSL-Integration in Docker Desktop. Für Python, Tests und die Pipeline geht es auch direkt unter Windows: uv mit `winget install astral-sh.uv`; `make` fehlt dort, die Befehle aus dem `Makefile` laufen auch einzeln (z. B. `uv run pytest -m "not integration"`). In Verbindungs-URLs `127.0.0.1` statt `localhost` schreiben: `localhost` versucht unter Windows zuerst IPv6 und hängt bei Ports aus Docker.

## Setup

```bash
git clone https://github.com/edu008/Dreamers4OpenParl.git
cd Dreamers4OpenParl
make setup          # uv sync: Python 3.12 und alle Abhängigkeiten aus uv.lock
cp .env.example .env # LLM_API_KEY eintragen; LLM_BASE_URL zeigt auf das Keera-Gateway
make db             # PostgreSQL 16 mit pgvector im Container
make migrate        # Schema anlegen
make data           # OpenParlData laden (~6 GB, inkl. Dokumente) und importieren
make test           # Unit-Tests
make web-build      # Web-App: npm ci beim ersten Mal, Build nach web/dist
```

`make data` lädt Parlamente, Geschäfte, Texte und Dokumente nach `data/import` und importiert sie. Ein zweiter Lauf lädt und schreibt nur, was sich geändert hat. Nur einzelne Parlamente: `uv run parltopics download --bodies CHE --bodies ZH`.

Danach:

```bash
uv run parltopics llm check   # erreicht der LLM-Endpunkt beide Modelle?
make api                      # API auf http://127.0.0.1:8000, liefert den Build aus web/dist aus
make web-dev                  # Vite mit Hot Reload auf http://127.0.0.1:5173, /v1 geht an make api
make help                     # alle Ziele
```

Die API-Dokumentation für die Web-App steht nach `make api` unter <http://127.0.0.1:8000/v1/docs> (Swagger UI aus dem Paket, ohne CDN); das Schema unter `/v1/openapi.json`.

Review-Entscheide schreibt `POST /v1/reviews` (bestätigen, verwerfen, ändern, hinzufügen, zurücknehmen), die offenen Fälle liefert `GET /v1/reviews/queue`. Im Hack-MVP gibt es keine Anmeldung und keine Rollen: Wer die API erreicht, kann entscheiden; an jedem Entscheid stehen Name und Zeit, und jeder lässt sich mit `undo` zurücknehmen. Die Aktion `undo` braucht Migration 0004: Auf der gemeinsamen Datenbank führt die betreibende Person `make migrate` aus.

Die Volltextsuche `GET /v1/search` (de, fr, it, ohne LLM) liest `search_documents`. Das füllt `parltopics inputs` gleich mit; Klassifikationstexte, die vor dieser Version gebaut wurden, bekommen ihr Dokument beim nächsten `inputs`-Lauf mit denselben Filtern.

## Klassifikation

Nach dem Ingest läuft die Pipeline in drei Kommandos (PRD 7.1, [ARCHITEKTUR.md](ARCHITEKTUR.md#2-pipeline)):

```bash
uv run parltopics registry sync                          # tags.yaml in die Tabelle tags, je registry_version einmal
uv run parltopics inputs --body CHE --since 2026-01-01   # Klassifikationstexte (affair_inputs) und Volltext
uv run parltopics classify --task classify:aps --body CHE --since 2026-01-01 --limit 20
uv run parltopics jobs summary                           # Jobs je Aufgabe und Status
uv run parltopics proposals group                        # Tag-Vorschläge gruppieren und prüfen (F7)
```

`classify` öffnet die Jobs eines Laufs und arbeitet sie mit `--wait` (Standard) gleich ab; je Geschäft erscheint eine Logzeile mit Status, Stufe und Grund einer Eskalation. Mit `--no-wait` übernehmen Worker die Jobs, auch mehrere parallel: `uv run parltopics worker --task classify:aps --once` endet, sobald keine Jobs mehr offen sind. Ein zweiter Aufruf mit denselben Filtern öffnet nichts, solange sich Text, Prompt und Registry nicht ändern.

Ein Ad-hoc-Thema (PRD 7.4) legt `uv run parltopics adhoc "Velowege" --description-file velo.txt --body CHE` an: 70B schlägt Stichwörter in DE/FR/IT vor (oder `--keywords-file` mit `{"de": [], "fr": [], "it": []}`), das Kommando zeigt Kandidaten und Stichprobe und fragt vor dem Anlegen. Das Tag steht danach mit Status `proposed` in `registry/tags.yaml`, die Jobs `classify:adhoc:<name>` sind offen; `--wait` arbeitet sie gleich ab. Bewährt sich das Thema: `uv run parltopics registry activate adhoc:velowege`. Dasselbe geht über die API (`/v1/adhoc/keywords`, `/v1/adhoc/preview`, `/v1/adhoc`, `/v1/adhoc/{tag_id}/activate`). Weil beides `registry/tags.yaml` ändert, die Datei danach committen.

### Qualität prüfen: Curia-Vista-Check

Für APS gibt es keine Gold-Labels. Als grobe Kontrolle dienen die Curia-Vista-Sachbereiche, die die Parlamentsdienste jedem Bundesgeschäft zuordnen (Hack-Datensatz, PRD 13). Die Zuordnung der 28 Sachbereiche zu den APS-Kapiteln steht in `registry/aps_descriptions.yaml` (`close_match`, `broad_match`); Themen erben sie von ihrem Kapitel.

```bash
mkdir -p data/import/hackapertus
curl -o data/import/hackapertus/che_affairs_keywords.csv https://files.openparldata.ch/hackapertus/che_affairs_keywords.csv
uv run parltopics eval --curia data/import/hackapertus/che_affairs_keywords.csv            # alle aktiven Labels, CHE ab 2024
uv run parltopics eval --curia data/import/hackapertus/che_affairs_keywords.csv --run 3    # nur ein Lauf
```

Gezählt werden nur APS-Labels. „Mindestens ein Treffer“ ist die Kennzahl aus PRD 13 (Ziel 75 %). Der Check ist grob: Er prüft nur das Kapitel, nicht das Thema, und Curia Vista ist selbst keine unabhängige Wahrheit. Für Vergleiche immer dieselben Geschäfte nehmen; bei unter 500 Geschäften schwanken die Zahlen um einige Prozentpunkte.

Ohne LLM-Endpunkt hilft der Mock aus den Tests: `uv run uvicorn app:app --app-dir tests/mock_llm --port 8080` und in `.env` `LLM_BASE_URL=http://127.0.0.1:8080/v1`. Er wählt immer das erste angebotene Kapitel und Thema.

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
2. In `.env` die gemeinsame Datenbank eintragen: die bestehende Zeile `DATABASE_URL` ersetzen, keine zweite anhängen, denn bei doppelten Schlüsseln gilt still die letzte. Das Passwort gibt es von der betreibenden Person über einen sicheren Kanal (Passwort-Manager, Signal), nie im Repo oder Chat-Verlauf:

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
