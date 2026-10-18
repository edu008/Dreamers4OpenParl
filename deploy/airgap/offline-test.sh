#!/usr/bin/env bash
# Offline-Test (PRD F22, AIRGAP.md 4): Betrieb in einem Docker-Netz ohne Route nach aussen.
# Voraussetzung: Image parltopics-app:${PARLTOPICS_VERSION:-dev} ist gebaut (make image).
set -euo pipefail
cd "$(dirname "$0")/../.."

COMPOSE=(docker compose -p parltopics-offline
  -f deploy/docker-compose.yml -f deploy/docker-compose.offline.yml --profile app)
cleanup() { "${COMPOSE[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
step() { printf '\n== %s\n' "$*"; }

step "Dienste im internen Netz starten: db, mock-llm, api"
"${COMPOSE[@]}" up --detach --wait db mock-llm api

step "Migration"
"${COMPOSE[@]}" exec -T api parltopics db migrate

step "Registry prüfen"
"${COMPOSE[@]}" exec -T api parltopics registry validate

step "LLM-Endpunkt (Mock) erreichbar"
"${COMPOSE[@]}" exec -T api parltopics llm check

step "Web-App antwortet: SPA aus web/dist, Routen, Assets, Seitenbaum"
"${COMPOSE[@]}" exec -T api python - <<'PY'
import json
import re
import urllib.request


def get(path: str) -> str:
    with urllib.request.urlopen(f"http://localhost:8000{path}", timeout=5) as response:
        return response.read().decode()


print("healthz:", get("/healthz"))
html = get("/")
assert 'id="root"' in html, "index.html der SPA fehlt"
assert not re.search(r'(?:src|href)="(?:https?:)?//', html), "index.html lädt von aussen"
assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
assert assets, "index.html verweist auf keine Assets"
for asset in assets:
    get(asset)
assert 'id="root"' in get("/tags/aps:6.1.9"), "SPA-Fallback für /tags/... fehlt"
assert json.loads(get("/v1/pages"))["pages"][0]["page_id"] == "heart"
print(f"ok: SPA mit {len(assets)} Assets, Fallback und Seitenbaum")
PY

step "Internet ist nicht erreichbar"
if "${COMPOSE[@]}" exec -T api python -c \
  "import urllib.request; urllib.request.urlopen('https://pypi.org/simple/', timeout=5)"; then
  echo "FEHLER: der App-Container erreicht das Internet" >&2
  exit 1
fi
echo "ok: kein Zugang nach aussen"

step "Allowlist im HTTP-Client"
"${COMPOSE[@]}" exec -T api python - <<'PY'
import asyncio

import httpx

from parltopics.llm import AllowlistTransport, HostNotAllowedError


async def main() -> None:
    async with httpx.AsyncClient(transport=AllowlistTransport(["mock-llm"])) as client:
        try:
            await client.get("https://example.org/")
        except HostNotAllowedError as error:
            print("ok:", error)
            return
    raise SystemExit("FEHLER: fremder Host wurde nicht blockiert")


asyncio.run(main())
PY

printf '\nOffline-Test bestanden.\n'
