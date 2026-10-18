# Architektur-Entscheide (ADR)

Jede Datei hält einen Entscheid fest: Kontext, Entscheid, Folgen, verworfene Alternativen. Ein Entscheid wird nicht überschrieben. Ändert er sich, kommt ein neuer ADR mit Verweis auf den alten.

| Nr. | Entscheid | Status |
|---|---|---|
| [0001](0001-registry-yaml.md) | Tag-Registry als YAML-Liste statt Markdown | angenommen |
| [0002](0002-postgres-queue.md) | PostgreSQL als Job-Queue statt Redis oder Celery | angenommen |
| [0003](0003-keine-embeddings-v1.md) | Keine Embeddings in Version 1 | angenommen |
| [0004](0004-scheme-hash.md) | Jobs hängen am `scheme_hash`, nicht an der `registry_version` | angenommen |
| [0005](0005-worker-und-agent.md) | Deterministische Worker für den Bestand, Tool-Calling-Agent für den Dialog | angenommen |
