# Air-Gap-Betrieb

ParlTopics ist für die Zielarchitektur **b) Air-gapped** des Hack-Templates ausgelegt: Zur Laufzeit gibt es keine Verbindung nach aussen ausser zum LLM-Endpunkt aus `LLM_BASE_URL`. Im echten Air-Gap-Betrieb steht auch dieser Endpunkt im internen Netz. Dieses Dokument beschreibt, was wann wo gebraucht wird, wie das Bundle entsteht und wie der Offline-Betrieb nachgewiesen wird.

Diagramm: [08-airgap-deployment](architecture/08-airgap-deployment.html). Anforderungen: PRD 5, 9, 10.3 und F22.

## 1. Abhängigkeiten nach Phase

| Was | Woher | Wann | Im Bundle |
|---|---|---|---|
| Python-Pakete | PyPI, gepinnt in `uv.lock` | Build | `wheels/` mit `requirements.txt` |
| Basis-Images | Docker Hub: `python:3.12-slim`, `pgvector/pgvector:pg16` | Build | `images/*.tar` |
| App-Image | gebaut aus `wheels/` | Build | `images/parltopics-app.tar` |
| Parlamentsdaten | `files.openparldata.ch` | Datendownload | separat, `data/import/` |
| Diagramme | Archify liegt im Repo, Node.js 18+ | nur Dokumentation | fertige HTML-Dateien |
| LLM | Keera (Hack) oder interner Endpunkt (Air-Gap) | Laufzeit | nein |

Zur Laufzeit lädt die Anwendung nichts nach: keine Pakete, keine Modelle, keine Schriften, keine Skripte von CDNs, keine Telemetrie. Die Spracherkennung (`lingua-language-detector`) bringt ihre Modelle im Wheel mit. Die Web-App liefert CSS und JavaScript selbst aus.

## 2. Ablauf

### 2.1 Bundle bauen (Rechner mit Internet)

```bash
make bundle
```

Das ruft [`deploy/airgap/build-bundle.sh`](../deploy/airgap/build-bundle.sh) auf:

1. `build-wheels.sh` exportiert die gepinnten Abhängigkeiten aus `uv.lock` und lädt die Wheels in einem `python:3.12-slim`-Container. So passen Plattform und Python-Version genau zum Image. Dazu kommt das Wheel des Projekts selbst.
2. `docker build` baut das App-Image ausschliesslich aus diesen Wheels (`pip install --no-index`). Ein Build, der etwas nachladen müsste, schlägt fehl.
3. Die Images `parltopics-app`, `pgvector/pgvector:pg16` und `python:3.12-slim` werden mit `docker save` exportiert. Das Basis-Image ist dabei, damit das App-Image auch offline neu gebaut werden kann.
4. Compose-Dateien, Dockerfile, `migrations/`, `prompts/`, `registry/tags.yaml`, `.env.example` und `load-bundle.sh` kommen dazu.
5. `SHA256SUMS` hält die Prüfsummen aller Dateien fest.

Ergebnis: `dist/parltopics-bundle-<version>.tar`. Grösse grob: Images rund 1 GB, Wheels einige hundert MB.

### 2.2 Daten holen (Rechner mit Internet)

```bash
uv run parltopics download --bundle data/import --bodies CHE
```

Das Import-Bündel ist ein normales Verzeichnis. Es wird getrennt vom Software-Bundle übertragen, weil es sich täglich ändert. Die Exporte (CHE etwa 300 MB) und optional die Dokumenttexte (5.5 GB) bestimmen die Grösse.

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

`load-bundle.sh` prüft zuerst `SHA256SUMS` und bricht bei einer Abweichung ab. Beim ersten Mal legt es `/srv/parltopics/.env` aus `.env.example` an und trägt `REGISTRY_DIR`, `IMPORT_DIR` und `PARLTOPICS_ENV_FILE` ein. Das Import-Bündel kommt nach `/srv/parltopics/import` und ist im Container schreibgeschützt unter `/data/import` eingebunden. Ab Meilenstein M0 folgen `registry sync` und `ingest --bundle /data/import`, ab M1 der Dienst `worker` (`--profile worker`).

### 2.5 Updates

Ein neues Bundle in ein eigenes Verzeichnis entpacken und `./load-bundle.sh /srv/parltopics` erneut ausführen. Das Skript lädt die neuen Images und setzt `PARLTOPICS_VERSION` in `.env` auf die neue Version. Danach startet `$COMPOSE --profile app up -d` die Dienste mit den neuen Images. Migrationen sind nummeriert und werden nur einmal angewendet. Die Datenbank liegt im Volume `pgdata` und bleibt erhalten.

Die Registry liegt im Basisverzeichnis und ist als Bind-Mount eingebunden. `load-bundle.sh` legt `tags.yaml` dort nur an, wenn die Datei fehlt. Spätere Bundles überschreiben also keine Review-Änderungen. Änderungen an der Registry im Betrieb sichert ein Mensch zurück ins Repo (PRD 7.2).

## 3. LLM-Endpunkt

| Betrieb | `LLM_BASE_URL` | Bemerkung |
|---|---|---|
| Hack | Keera, OpenAI-kompatibel | einzige Verbindung nach aussen |
| Air-Gap | interner Endpunkt, z. B. vLLM | keine Verbindung nach aussen |
| Tests | Mock im internen Docker-Netz | siehe Abschnitt 4 |

Für den internen Endpunkt liegt eine Vorlage in [`deploy/docker-compose.llm.yml`](../deploy/docker-compose.llm.yml). Sie ist **im Hack nicht getestet** und braucht eine GPU. Die Gewichte von Apertus v1.5 (Apache 2.0) werden online von Hugging Face geladen, übertragen und schreibgeschützt eingebunden; sie gehören nicht ins Repo (`.gitignore` schliesst `*.safetensors` aus). Grobe Grössenordnung in bf16: 8B rund 16 GB GPU-Speicher, 70B rund 140 GB, also mehrere GPUs oder Quantisierung. Die vLLM-Version muss Apertus unterstützen und ist vor dem Einsatz festzulegen.

## 4. Nachweis

| Prüfung | Wie | Wo |
|---|---|---|
| Allowlist | Unit-Test: der Client verweigert jeden Host ausser dem aus `LLM_BASE_URL` | `tests/unit/test_llm_client.py` |
| Image ohne PyPI | Dockerfile installiert mit `--no-index` aus `wheels/` | `deploy/Dockerfile` |
| Betrieb ohne Internet | Offline-Test im internen Docker-Netz | `make offline-test`, CI-Job `offline` |

Der Offline-Test ([`deploy/airgap/offline-test.sh`](../deploy/airgap/offline-test.sh)) startet `db`, `api` und einen Mock-LLM in einem Docker-Netz mit `internal: true`. Darin gibt es keine Route nach aussen, die Container erreichen sich aber gegenseitig. Der Test prüft:

1. `parltopics db migrate` legt das Schema an.
2. `parltopics registry validate` liest `registry/tags.yaml`.
3. `parltopics llm check` erreicht den Mock-LLM.
4. Die Web-App antwortet auf `/healthz`.
5. Ein Aufruf ins Internet aus dem App-Container scheitert.

## 5. Checkliste

- [ ] Keine `<script src="http…">`, `<link href="http…">` oder Web-Fonts in Templates.
- [ ] Neue Python-Abhängigkeit: Wheel für `linux/amd64`, Python 3.12 vorhanden? `make wheels` zeigt es.
- [ ] Keine Bibliothek, die zur Laufzeit Modelle oder Daten herunterlädt.
- [ ] Neue externe Hosts nur über `LLM_BASE_URL`; sonst ist es ein Fehler.
- [ ] Offline-Test grün.
