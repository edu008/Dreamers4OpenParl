# Daten

Dieses Verzeichnis ist nicht im Repo, nur diese Datei. Grund: Die Nutzungsbedingungen von OpenParlData und der PolitMonitor-Daten sind noch offen (PRD 15), und die Exporte sind gross.

| Ordner | Inhalt | Entsteht durch |
|---|---|---|
| `import/` | Import-Bündel: OpenParlData-Exporte, hackapertus-Datensatz | `uv run parltopics download --bundle data/import --bodies CHE` |
| `gold/` | Gold-Set, Korrektur-Exporte aus dem Review | Review, Team |

Das Mapping APS ↔ Curia Vista steht seit PRD 0.4 in der Registry (`exact_match`, `close_match`, `broad_match` in `registry/tags.yaml`) und ersetzt die geplante Datei `gold/aps_curia_mapping.csv`. Eine Person aus dem Team prüft es vor der Messung; die Messung friert die `registry_version` ein (PRD 13).
