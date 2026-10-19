# Air-Gap-Betrieb

ParlTopics ist für die Zielarchitektur **b) Air-gapped** des Hack-Templates ausgelegt: Zur Laufzeit gibt es keine Verbindung nach aussen ausser zum LLM-Endpunkt aus `LLM_BASE_URL`. Im echten Air-Gap-Betrieb steht auch dieser Endpunkt im internen Netz. Dieses Dokument beschreibt, was wann wo gebraucht wird, wie das Bundle entsteht und wie der Offline-Betrieb nachgewiesen wird.

Diagramm: [08-airgap-deployment](architecture/08-airgap-deployment.html). Anforderungen: PRD 5, 9, 10.3 und F22.

## 1. Abhängigkeiten nach Phase

| Was | Woher | Wann | Im Bundle |
|---|---|---|---|
| Python-Pakete | PyPI, gepinnt in `uv.lock` | Build | `wheels/` mit `requirements.txt` |
| Basis-Images | Docker Hub: `python:3.12-slim`, `pgvector/pgvector:pg16` | Build | `images/*.tar` |
| Web-App | npm-Registry, gepinnt in `web/package-lock.json`, Node 22 | Build (`make web-build`) | `web/dist/`, auch im App-Image |
| App-Image | gebaut aus `wheels/` und `web/dist/` | Build | `images/parltopics-app.tar` |
| Parlamentsdaten | `files.openparldata.ch` | Datendownload | separat, `data/import/` |
| Diagramme | Archify liegt im Repo, Node.js 18+ | nur Dokumentation | fertige HTML-Dateien |
| LLM | Keera (Hack) oder interner Endpunkt (Air-Gap) | Laufzeit | nein |

Zur Laufzeit lädt die Anwendung nichts nach: keine Pakete, keine Modelle, keine Schriften, keine Skripte von CDNs, keine Telemetrie. Die Spracherkennung (`lingua-language-detector`) bringt ihre Modelle im Wheel mit. Die Web-App ist ein statischer Build (React, Vite, shadcn/ui) und liegt im App-Image; FastAPI liefert HTML, CSS und JavaScript selbst aus. Sie nutzt Systemschriften und lädt nichts von einem CDN. `scripts/check-web-dist.mjs` prüft den Build auf externe URLs: erlaubt sind nur Hosts, die nie geladen werden, etwa XML-Namensräume und Doku-Links in Fehlermeldungen. Ein Neubau der Web-App im Air-Gap ist nicht vorgesehen, weil er die npm-Registry bräuchte; das Bundle enthält den fertigen Build.

## 2. Ablauf

### 2.1 Bundle bauen (Rechner mit Internet)

```bash
make bundle
```

Das ruft [`deploy/airgap/build-bundle.sh`](../deploy/airgap/build-bundle.sh) auf:

1. `build-wheels.sh` exportiert die gepinnten Abhängigkeiten aus `uv.lock` und lädt die Wheels in einem `python:3.12-slim`-Container. So passen Plattform und Python-Version genau zum Image. Dazu kommt das Wheel des Projekts selbst.
2. `npm ci` und `npm run build` bauen die Web-App nach `web/dist`, danach prüft `check-web-dist.mjs` den Build auf externe URLs.
3. `docker build` baut das App-Image ausschliesslich aus diesen Wheels (`pip install --no-index`) und `web/dist`. Ein Build, der etwas nachladen müsste, schlägt fehl.
4. Die Images `parltopics-app`, `pgvector/pgvector:pg16` und `python:3.12-slim` werden mit `docker save` exportiert. Das Basis-Image ist dabei, damit das App-Image auch offline neu gebaut werden kann.
5. Compose-Dateien, Dockerfile, `migrations/`, `prompts/`, `registry/tags.yaml`, `web/dist/`, `.env.example` und `load-bundle.sh` kommen dazu.
6. `SHA256SUMS` hält die Prüfsummen aller Dateien fest.

Ergebnis: `dist/parltopics-bundle-<version>.tar`, die Version stammt aus `git describe`. In der CI gemessen: rund 1,4 GB, davon 183 MB Wheels (43 Dateien), der Rest sind die drei Images.

### 2.2 Daten holen (Rechner mit Internet)

```bash
uv run parltopics download --bundle data/import --bodies CHE
```

Das Import-Bündel ist ein normales Verzeichnis. Es wird getrennt vom Software-Bundle übertragen, weil es sich täglich ändert. Die Exporte (CHE etwa 350 MB, davon 58 MB Beteiligte aller Parlamente) und optional die Dokumenttexte (5.5 GB) bestimmen die Grösse.

### 2.3 Transfer

Software-Bundle und Import-Bündel auf einen Datenträger kopieren. Auf der Gegenseite prüft `load-bundle.sh` die Prüfsummen, bevor etwas geladen wird.

### 2.4 Einspielen (Server ohne Internet)

Ein Basisverzeichnis, z. B. `/srv/parltopics`, bleibt über alle Bundles bestehen. Es enthält `.env`, `registry/` und `import/`.

```bash
tar -xf parltopics-bundle-<version>.tar
cd parltopics-bundle-<version>
./load-bundle.sh /srv/parltopics        # Prüfsummen, docker load, Basisverzeichnis anlegen
# In /srv/parltopics/.env eintragen: LLM_BASE_URL, LLM_API_KEY, POSTGRES_PASSWORD
COMPOSE="docker compose --env-file /srv/parltopics/.env -f deploy/docker-compose.yml"
$COMPOSE --profile app up -d
$COMPOSE exec api parltopics db migrate
$COMPOSE exec api parltopics registry validate
$COMPOSE exec api parltopics llm check
```

`load-bundle.sh` prüft zuerst `SHA256SUMS` und bricht bei einer Abweichung ab. Beim ersten Mal legt es `/srv/parltopics/.env` aus `.env.example` an und trägt `REGISTRY_DIR`, `IMPORT_DIR` und `PARLTOPICS_ENV_FILE` ein. Das Import-Bündel kommt nach `/srv/parltopics/import` und ist im Container schreibgeschützt unter `/data/import` eingebunden. Danach folgen `$COMPOSE exec api parltopics registry sync`, `ingest --bundle /data/import` und `inputs`; den Dienst `worker` startet `$COMPOSE --profile worker up -d`. Die API-Dokumentation (Swagger UI) liefert das Image unter `/v1/docs` selbst aus, ohne CDN.

### 2.5 Updates

Ein neues Bundle in ein eigenes Verzeichnis entpacken und `./load-bundle.sh /srv/parltopics` erneut ausführen. Das Skript lädt die neuen Images und setzt `PARLTOPICS_VERSION` in `.env` auf die neue Version. Danach startet `$COMPOSE --profile app up -d` die Dienste mit den neuen Images. Migrationen sind nummeriert und werden nur einmal angewendet. Die Datenbank liegt im Volume `pgdata` und bleibt erhalten.

Die Registry liegt im Basisverzeichnis und ist als Bind-Mount eingebunden. `load-bundle.sh` legt `tags.yaml` dort nur an, wenn die Datei fehlt. Spätere Bundles überschreiben also keine Review-Änderungen. Änderungen an der Registry im Betrieb sichert ein Mensch zurück ins Repo (PRD 7.2).

## 3. LLM-Endpunkt

| Betrieb | `LLM_BASE_URL` | Bemerkung |
|---|---|---|
| Hack | Keera, OpenAI-kompatibel: `https://gateway.keera.ch/api/v1` | einzige Verbindung nach aussen; die URL steht in `.env.example` |
| Air-Gap | interner Endpunkt, z. B. vLLM | keine Verbindung nach aussen |
| Tests | Mock im internen Docker-Netz | siehe Abschnitt 4 |

Für den internen Endpunkt liegt eine Vorlage in [`deploy/docker-compose.llm.yml`](../deploy/docker-compose.llm.yml). Sie ist **im Hack nicht getestet** und braucht eine GPU. Die Gewichte von Apertus v1.5 (Apache 2.0) werden online von Hugging Face geladen, übertragen und schreibgeschützt eingebunden; sie gehören nicht ins Repo (`.gitignore` schliesst `*.safetensors` aus). Grobe Grössenordnung in bf16: 8B rund 16 GB GPU-Speicher, 70B rund 140 GB, also mehrere GPUs oder Quantisierung. Die vLLM-Version muss Apertus unterstützen und ist vor dem Einsatz festzulegen.

## 4. Nachweis

| Prüfung | Wie | Wo |
|---|---|---|
| Allowlist | Unit-Test: der Client verweigert jeden Host ausser dem aus `LLM_BASE_URL` | `tests/unit/test_llm_client.py` |
| Image ohne PyPI | Dockerfile installiert mit `--no-index` aus `wheels/` | `deploy/Dockerfile` |
| Betrieb ohne Internet | Offline-Test im internen Docker-Netz | `make offline-test`, CI-Job `offline` |
| Web-App ohne externe URLs | Prüfung des Builds | `scripts/check-web-dist.mjs`, `make web-build`, CI-Job `web` |

Der Offline-Test ([`deploy/airgap/offline-test.sh`](../deploy/airgap/offline-test.sh)) startet `db`, `api` und einen Mock-LLM in einem Docker-Netz mit `internal: true`. Darin gibt es keine Route nach aussen, die Container erreichen sich aber gegenseitig. Der Test prüft:

1. `parltopics db migrate` legt das Schema an.
2. `parltopics registry validate` liest `registry/tags.yaml`.
3. `parltopics llm check` erreicht den Mock-LLM.
4. Die Web-App antwortet: `/healthz`, die SPA aus `web/dist` mit ihren Assets, der SPA-Fallback für `/admin/themen/aps:6.1.9` und der Seitenbaum unter `/v1/pages`. `index.html` lädt nichts von aussen.
5. Ein Aufruf ins Internet aus dem App-Container scheitert.

## 5. Checkliste

- [ ] Keine `<script src="http…">`, `<link href="http…">` oder Web-Fonts in der Web-App; `make web-build` meldet jeden neuen Host.
- [ ] Neue npm-Abhängigkeit: nur zur Build-Zeit nötig, Lizenz geprüft, `npm audit --omit=dev` ohne Befund.
- [ ] Neue Python-Abhängigkeit: Wheel für `linux/amd64`, Python 3.12 vorhanden? `make wheels` zeigt es.
- [ ] Keine Bibliothek, die zur Laufzeit Modelle oder Daten herunterlädt.
- [ ] Neue externe Hosts nur über `LLM_BASE_URL`; sonst ist es ein Fehler.
- [ ] Offline-Test grün.
