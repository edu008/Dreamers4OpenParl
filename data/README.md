# Daten

Dieses Verzeichnis ist nicht im Repo, nur diese Datei. Grund: Die Nutzungsbedingungen von OpenParlData und der PolitMonitor-Daten sind noch offen (PRD 15), und die Exporte sind gross.

| Ordner | Inhalt | Entsteht durch |
|---|---|---|
| `import/` | Import-Bündel: OpenParlData-Exporte, hackapertus-Datensatz | `uv run parltopics download --bundle data/import --bodies CHE` |
| `gold/` | Gold-Set, Korrektur-Exporte aus dem Review, `aps_curia_mapping.csv` | Review, Team |

Das Mapping APS ↔ Curia Vista (`gold/aps_curia_mapping.csv`) wird vor der Messung von einer Person aus dem Team geprüft und eingefroren (PRD 13). Wenn die Lizenz geklärt ist, kann es mit `git add -f` ins Repo.
