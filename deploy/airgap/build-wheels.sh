#!/usr/bin/env bash
# Lädt alle Laufzeit-Abhängigkeiten als Wheels nach deploy/airgap/wheels (PRD F22, AIRGAP.md 2.1).
# Läuft auf einem Rechner mit Internet. Die Wheels werden in einem Container des Ziel-Images geladen,
# damit Plattform und Python-Version genau zum App-Image passen. Nur Wheels, keine Quellpakete.
set -euo pipefail
cd "$(dirname "$0")/../.."

PYTHON_IMAGE="${PYTHON_IMAGE:-python:3.12-slim}"
OUT=deploy/airgap/wheels

rm -rf "$OUT"
mkdir -p "$OUT"
uv export --frozen --no-dev --no-emit-project --format requirements-txt \
  --output-file "$OUT/requirements.txt" >/dev/null
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/$OUT:/wheels" "$PYTHON_IMAGE" \
  pip download --disable-pip-version-check --no-cache-dir --only-binary=:all: \
  --dest /wheels --requirement /wheels/requirements.txt
uv build --wheel --out-dir "$OUT" >/dev/null
echo "Wheels in $OUT: $(find "$OUT" -name '*.whl' | wc -l) Dateien, $(du -sh "$OUT" | cut -f1)"
