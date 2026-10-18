#!/usr/bin/env bash
# Spielt ein Air-Gap-Bundle auf einem Server ohne Internet ein (AIRGAP.md 2.4).
#   ./load-bundle.sh <basisverzeichnis>
# Das Basisverzeichnis bleibt über alle Bundles bestehen und enthält .env, registry/ und import/.
set -euo pipefail
cd "$(dirname "$0")"

if [ $# -ne 1 ]; then
  echo "Aufruf: $0 <basisverzeichnis>   z. B. $0 /srv/parltopics" >&2
  exit 2
fi
BASE="$(mkdir -p "$1" && cd "$1" && pwd)"
VERSION="$(cat VERSION)"

echo "Prüfsummen ..."
sha256sum --check --quiet SHA256SUMS

for image in images/*.tar; do
  docker load --input "$image"
done

mkdir -p "$BASE/registry" "$BASE/import"
if [ -f "$BASE/registry/tags.yaml" ]; then
  echo "Registry bleibt unverändert: $BASE/registry/tags.yaml"
else
  cp registry/tags.yaml "$BASE/registry/tags.yaml"
  echo "Registry angelegt: $BASE/registry/tags.yaml"
fi

ENV_FILE="$BASE/.env"
if [ ! -f "$ENV_FILE" ]; then
  sed -e "s|^REGISTRY_DIR=.*|REGISTRY_DIR=$BASE/registry|" \
      -e "s|^IMPORT_DIR=.*|IMPORT_DIR=$BASE/import|" \
      -e "s|^PARLTOPICS_ENV_FILE=.*|PARLTOPICS_ENV_FILE=$ENV_FILE|" \
      .env.example > "$ENV_FILE"
  echo "Konfiguration angelegt: $ENV_FILE (LLM_BASE_URL, LLM_API_KEY, POSTGRES_PASSWORD eintragen)"
fi
if grep -q '^PARLTOPICS_VERSION=' "$ENV_FILE"; then
  sed -i "s|^PARLTOPICS_VERSION=.*|PARLTOPICS_VERSION=$VERSION|" "$ENV_FILE"
else
  printf 'PARLTOPICS_VERSION=%s\n' "$VERSION" >> "$ENV_FILE"
fi

echo
echo "Bundle $VERSION geladen. Starten mit:"
echo "  docker compose --env-file $ENV_FILE -f deploy/docker-compose.yml --profile app up -d"
