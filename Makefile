# ParlTopics – häufige Aufgaben. `make help` zeigt alle Ziele.
SHELL := /bin/bash
.DEFAULT_GOAL := help

UV ?= uv
PARLTOPICS_VERSION ?= dev
BUNDLE_VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo dev)
TEST_DATABASE_URL ?= postgresql://parltopics:parltopics@localhost:5432/parltopics
COMPOSE := docker compose $(if $(wildcard .env),--env-file .env) -f deploy/docker-compose.yml

export PARLTOPICS_VERSION
export ARCHIFY_UPDATE_CHECK_DISABLED := 1

.PHONY: help setup lint format test test-integration db db-down migrate api \
        diagrams diagrams-check wheels image offline-test bundle clean

help: ## Ziele anzeigen
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

setup: ## Python 3.12 und Abhängigkeiten aus uv.lock installieren
	$(UV) sync

lint: ## ruff check und Format-Prüfung
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## Code formatieren und einfache Fehler beheben
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

test: ## Unit-Tests
	$(UV) run pytest -m "not integration"

test-integration: ## Integrationstests gegen die Datenbank aus `make db`
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) $(UV) run pytest -m integration

db: ## PostgreSQL 16 mit pgvector im Container starten
	$(COMPOSE) up --detach --wait db

db-down: ## Container stoppen (Daten bleiben im Volume pgdata)
	$(COMPOSE) down

migrate: ## Migrationen anwenden
	$(UV) run parltopics db migrate

api: ## Web-App und API lokal mit Reload auf http://127.0.0.1:8000
	$(UV) run uvicorn parltopics.api.app:app --reload --host 127.0.0.1 --port 8000

diagrams: ## Diagramme mit Archify bauen (braucht Chrome oder Chromium)
	node scripts/diagrams.mjs build

diagrams-check: ## Diagramme prüfen: Schema und Aktualität der HTML-Dateien
	node scripts/diagrams.mjs check

wheels: ## Wheels für das Air-Gap-Image laden (online)
	deploy/airgap/build-wheels.sh

image: wheels ## App-Image aus den Wheels bauen
	docker build -f deploy/Dockerfile -t parltopics-app:$(PARLTOPICS_VERSION) .

offline-test: image ## Offline-Test in einem Docker-Netz ohne Internet
	deploy/airgap/offline-test.sh

bundle: ## Air-Gap-Bundle nach dist/ bauen (online), Version aus git describe
	PARLTOPICS_VERSION=$(BUNDLE_VERSION) deploy/airgap/build-bundle.sh

clean: ## Erzeugte Dateien entfernen
	rm -rf dist .archify deploy/airgap/wheels .pytest_cache .ruff_cache
