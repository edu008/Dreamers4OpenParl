# ADR 0004: Jobs hängen am `scheme_hash`, nicht an der `registry_version`

- Status: angenommen; die Feldnamen der kanonischen Form verfeinert [ADR 0007](0007-registry-skos.md); die Folge «Aktive Ad-hoc-Tags laufen in Stufe 2 von `classify:aps` mit» ersetzt [ADR 0009](0009-adhoc-eigene-jobs.md)
- Datum: 18.10.2026
- Bezug: PRD 7.2, 7.7, F18, ARCHITEKTUR.md 3.7

## Kontext

PRD 0.2 setzte Jobs auf `open`, sobald eine neue `registry_version` vorlag. Jede Änderung an der Registry erhöht diese Version, auch die Annahme eines einzelnen Ad-hoc-Vorschlags. Damit hätte jede Annahme alle 326'000 `classify:aps`-Jobs geöffnet, also einen Volllauf von bis zu 24 Stunden ausgelöst.

## Entscheid

Ein Job speichert den `scheme_hash` des Registry-Ausschnitts, den seine Aufgabe nutzt:

- `classify:aps`: SHA-256 über alle aktiven APS-Einträge.
- `classify:adhoc:<tag>` und `reclassify:<tag_id>`: SHA-256 über genau dieses Tag.

Gehashed wird die kanonische Form (`tag_id`, `parent`, `names`, `descriptions`, `aliases`), sortiert nach `tag_id`. Ein Job geht nur auf, wenn sich der Hash seiner Aufgabe ändert. Die `registry_version` bleibt als Protokollfeld an jedem Label.

## Folgen

- Ein neues oder geändertes Ad-hoc-Tag öffnet nur seine eigenen Jobs für Kandidaten und Stichprobe.
- Metadaten wie `created` oder `unreviewed_translations` ändern keinen Hash und lösen nichts aus.
- Aktive Ad-hoc-Tags laufen in Stufe 2 von `classify:aps` mit, ändern aber dessen Hash nicht. Bestehende Geschäfte erreicht ein neues Ad-hoc-Tag über `reclassify:<tag_id>`.

## Verworfene Alternativen

- **Version je Schema in der Datei:** müsste von Hand gepflegt werden und kann vergessen gehen. Der Hash entsteht automatisch.
