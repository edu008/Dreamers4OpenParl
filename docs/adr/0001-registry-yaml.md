# ADR 0001: Tag-Registry als YAML-Liste statt Markdown

- Status: angenommen
- Datum: 18.10.2026
- Bezug: PRD 7.2, Anhang A, F4

## Kontext

PRD 0.2 sah `tags.md` vor: eine Markdown-Datei mit eigenem Format (Überschrift mit Pipe-getrennten Namen, Listeneinträge für Felder). Die Datei soll für Menschen lesbar, in Git reviewbar und für die App maschinenlesbar sein.

## Entscheid

Die Registry ist `registry/tags.yaml`. Tags stehen als **Liste** unter `tags:`. Pydantic validiert die Datei (`src/parltopics/registry/models.py`).

## Folgen

- Kein eigener Parser, also keine eigene Fehlerquelle und keine Tests dafür.
- Gleiche Vorteile wie Markdown: lesbar, Git-Diffs, Review per Pull Request.
- Als Liste statt als Mapping, weil YAML-Parser doppelte Schlüssel in einem Mapping still überschreiben. Bei einer Liste findet die Validierung doppelte IDs (F4).
- Kommentare in der Datei gehen verloren, wenn die App sie neu schreibt. Erklärungen gehören deshalb in `descriptions` oder in die Doku.

## Verworfene Alternativen

- **Markdown (`tags.md`):** lesbarer für Nicht-Techniker, aber ein eigener Parser und ein Format, das niemand sonst kennt.
- **Nur Datenbank:** keine Historie und kein Review in Git.
