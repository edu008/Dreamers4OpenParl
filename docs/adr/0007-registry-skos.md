# ADR 0007: Registry nach SKOS

- Status: angenommen
- Datum: 18.10.2026
- Bezug: PRD 7.2, Anhang A, F4, F27; verfeinert ADR 0001 und ADR 0004

## Kontext

Die Registry hatte die Felder `names`, `descriptions`, `aliases` und `parent`. Synonyme und Schreibvarianten standen gemeinsam in `aliases`, die Hierarchie kannte nur ein Elternteil, und für „verwandt“ und die Zuordnung zu Curia-Vista-Sachbereichen gab es kein Feld. Das Mapping zu Curia Vista war als eigene CSV-Datei geplant. Das Konzept „Tag-Hierarchie mit Heart-Seite“ verlangt eine Registry nach SKOS, dem W3C-Standard für kontrollierte Vokabulare, den auch EuroVoc nutzt.

## Entscheid

- Felder nach SKOS: `pref_label` (ein Name je Sprache), `alt_labels` (Synonyme), `hidden_labels` (Schreibvarianten und Tippfehler), `definition`, `broader`, `related`, `exact_match`, `close_match`, `broad_match` (Curia-Vista-Sachbereiche als `curia:<id>`).
- `narrower` wird nicht gespeichert, sondern aus `broader` abgeleitet. Bei APS ist `broader` genau der Eltern-Code, Ad-hoc-Tags dürfen mehrere APS-Kapitel oder -Themen als `broader` haben. `related` und `broader` überschneiden sich nicht.
- APS-Tags erhalten einen festen `slug` für den Dateinamen ihrer Tag-Seite.
- Die Datei bleibt `registry/tags.yaml` mit Pydantic-Validierung (ADR 0001).
- Der `scheme_hash` umfasst `tag_id`, `broader`, `pref_label`, `alt_labels` und `definition`. `hidden_labels`, `related` und die Mappings stehen nicht im Prompt und ändern ihn nicht; ADR 0004 gilt weiter.
- In der Datenbank bleibt die Tabelle `tags` aus 0001 bestehen. Labels, Beziehungen und Mappings stehen vollständig in `tag_labels`, `tag_relations` und `tag_mappings` (Migration 0002).

## Folgen

- Ein bekanntes Vokabularformat; ein späterer Export als SKOS ist einfach.
- Das Mapping zu Curia Vista ist versioniert und wird mit der Registry geprüft. Die Messung friert die `registry_version` ein.
- Schreibvarianten verbessern Suche und Duplikatprüfung, ohne Jobs neu zu öffnen.
- Prompts, Fixtures und die Registry-Datei wurden auf die neuen Namen umgestellt. Die v1-Prompts waren noch in keinem Lauf, deshalb ohne neue Versionsnummer.

## Verworfene Alternativen

- **Alte Feldnamen behalten und nur auf SKOS abbilden:** kein Umbau, aber zwei Begriffssysteme im Team und in den Prompts.
- **Registry als RDF (Turtle):** Standardformat, aber ohne direkte Pydantic-Validierung und für das Team schwerer zu lesen und zu prüfen.
- **Mapping zu Curia Vista als eigene CSV:** eine zweite Datei mit eigener Versionierung neben der Registry.
