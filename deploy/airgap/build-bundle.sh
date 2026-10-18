#!/usr/bin/env bash
# Baut das Air-Gap-Bundle (PRD F22, AIRGAP.md 2.1): Images, Wheels, Compose-Dateien, Migrationen,
# Prompts, Start-Registry und Prüfsummen. Läuft auf einem Rechner mit Internet.
set -euo pipefail
cd "$(dirname "$0")/../.."

VERSION="${PARLTOPICS_VERSION:-$(git describe --tags --always --dirty 2>/dev/null || echo dev)}"
PYTHON_IMAGE="${PYTHON_IMAGE:-python:3.12-slim}"
DB_IMAGE="${DB_IMAGE:-pgvector/pgvector:pg16}"
NAME="parltopics-bundle-$VERSION"
STAGE="dist/$NAME"

deploy/airgap/build-wheels.sh
docker pull "$PYTHON_IMAGE"
docker pull "$DB_IMAGE"
docker build -f deploy/Dockerfile --build-arg PYTHON_IMAGE="$PYTHON_IMAGE" \
  -t "parltopics-app:$VERSION" .

rm -rf "$STAGE" "dist/$NAME.tar"
mkdir -p "$STAGE/images"
docker save -o "$STAGE/images/parltopics-app.tar" "parltopics-app:$VERSION"
docker save -o "$STAGE/images/pgvector.tar" "$DB_IMAGE"
docker save -o "$STAGE/images/python-base.tar" "$PYTHON_IMAGE"
cp -r deploy migrations prompts registry "$STAGE/"
cp .env.example "$STAGE/.env.example"
printf '%s\n' "$VERSION" > "$STAGE/VERSION"
cp deploy/airgap/load-bundle.sh "$STAGE/load-bundle.sh"
(cd "$STAGE" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
tar -C dist -cf "dist/$NAME.tar" "$NAME"
echo "Bundle: dist/$NAME.tar ($(du -h "dist/$NAME.tar" | cut -f1))"
